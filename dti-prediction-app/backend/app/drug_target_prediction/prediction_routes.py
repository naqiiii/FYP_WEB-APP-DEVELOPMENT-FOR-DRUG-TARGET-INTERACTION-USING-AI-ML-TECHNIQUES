import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.concurrency import run_in_threadpool
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.mongodb_connection import get_database
from app.user_authentication.jwt_bearer import get_current_user
from app.drug_target_prediction.prediction_schemas import (
    PredictionRequest, PredictionResponse, 
    BatchPredictionRequest, ProteinBatchPredictionRequest
)
from app.drug_target_prediction.real_ml_model import predict_dti, predict_dti_batch
from app.drug_target_prediction.translation_service import (
    translate_drug_name_to_smiles, translate_protein_name_to_sequence
)
from app.drug_target_prediction.molecular_properties import (
    calculate_drug_likeness, compute_protein_info
)

router = APIRouter(prefix="/api", tags=["Prediction"])
limiter = Limiter(key_func=get_remote_address)

def _generate_display_labels(drug_name, protein_name, smiles, sequence):
    """Build readable labels for the frontend from whatever the user entered."""
    dn = (drug_name or "").strip()
    pn = (protein_name or "").strip()
    
    # If the user gave a name, show it. Otherwise show the first part of the SMILES or sequence.
    label_drug = dn[:72] if dn else smiles[:56] + ("..." if len(smiles) > 56 else "")
    label_protein = pn if pn else f"Sequence ({len(sequence)} aa)"
    
    return label_drug, label_protein

def _is_below_checkpoint(log_affinity, checkpoint):
    """Reject predictions that do not meet the user's minimum affinity threshold."""
    if checkpoint is not None and log_affinity < checkpoint:
        return True
    return False

def truncate_drug_smiles(smiles: str) -> str:
    """Truncate smiles if it exceeds limits (350 characters)."""
    if smiles:
        s_stripped = smiles.strip()
        if len(s_stripped) > 350:
            print(f"[Info] Truncated drug SMILES from {len(s_stripped)} to 350 characters.")
            return s_stripped[:350]
        return s_stripped
    return smiles

def truncate_protein_sequence(sequence: str) -> str:
    """Truncate sequence if it exceeds limits (1022 amino acids)."""
    if sequence:
        seq_stripped = sequence.strip()
        if len(seq_stripped) > 1022:
            print(f"[Info] Truncated protein sequence from {len(seq_stripped)} to 1022 amino acids.")
            return seq_stripped[:1022]
        return seq_stripped
    return sequence

def _check_for_swapped_inputs(drug_raw: str, protein_raw: str):
    """Detect if drug and protein inputs are likely swapped and raise user-friendly errors."""
    if not drug_raw or not protein_raw:
        return

    amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    d_strip = drug_raw.strip()
    p_strip = protein_raw.strip()

    # 1. Check if the protein input looks like a drug SMILES
    has_smiles_chars = any(c in "=#()[]/\\+$@." for c in p_strip)
    has_lowercase = any(c.islower() for c in p_strip)
    has_numbers = any(c.isdigit() for c in p_strip)

    if has_smiles_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Input Error: The protein sequence or name field ('{p_strip[:30]}...') "
                "contains chemical structure symbols (like '=', '(', ')', '[', ']'). "
                "Please enter a valid protein sequence (e.g. MVLS...) or name."
            )
        )
    if len(p_strip) > 15 and has_lowercase and has_numbers:
        non_aa = sum(1 for c in p_strip.upper() if c not in amino_acids and c.isalpha())
        if non_aa > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Input Error: The protein sequence or name field ('{p_strip[:30]}...') "
                    "resembles a chemical formula or SMILES string. "
                    "Please enter a valid protein sequence or common name."
                )
            )

    # 2. Check if the drug input looks like a protein sequence
    d_upper = d_strip.upper()
    if len(d_strip) >= 20 and all(c in amino_acids for c in d_upper):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Input Error: The drug SMILES or name field ('{d_strip[:30]}...') "
                "resembles a protein sequence (consists entirely of uppercase amino acid letters). "
                "Please enter a valid drug name or SMILES string."
            )
        )

def _check_resolved_limits(smiles: str, sequence: str):
    """Placeholder since truncation is handled during input resolution."""
    pass

@router.post("/predict", response_model=PredictionResponse)
@limiter.limit("20/minute")
async def make_prediction(
    request: Request,
    body: PredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Calculate binding affinity for a single drug-protein pair."""
    
    # Check for swapped inputs first
    drug_raw = body.smiles or body.drug_name or ""
    protein_raw = body.sequence or body.protein_name or ""
    _check_for_swapped_inputs(drug_raw, protein_raw)

    # The user can either type a drug SMILES directly or just give a drug name.
    # If they provide a name, we convert it to SMILES behind the scenes.
    if body.smiles and body.smiles.strip():
        smiles = truncate_drug_smiles(body.smiles)
    elif body.drug_name and body.drug_name.strip():
        smiles = await translate_drug_name_to_smiles(body.drug_name.strip())
        smiles = truncate_drug_smiles(smiles)
    else:
        raise HTTPException(status_code=400, detail="Please provide a drug name or SMILES.")
        
    # Protein input can also be a name or a raw amino acid chain.
    # The model only understands sequences, so we translate names when needed.
    if body.sequence and body.sequence.strip():
        sequence = truncate_protein_sequence(body.sequence)
    elif body.protein_name and body.protein_name.strip():
        sequence = await translate_protein_name_to_sequence(body.protein_name.strip())
        sequence = truncate_protein_sequence(sequence)
    else:
        raise HTTPException(status_code=400, detail="Please provide a protein name or sequence.")

    # Validate resolved limits
    _check_resolved_limits(smiles, sequence)

    # The prediction function uses a heavy machine learning model.
    # We run it in a worker thread so the main server can keep handling other requests.
    try:
        result = await run_in_threadpool(predict_dti, drug_smiles=smiles, protein_sequence=sequence)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    # If the prediction is worse than the user's minimum threshold, stop here.
    # This saves time and avoids recording weak candidates.
    if _is_below_checkpoint(result["log_affinity"], body.min_affinity_checkpoint):
        raise HTTPException(
            status_code=400, 
            detail=f"Screening Filter: Predicted affinity ({result['log_affinity']}) is below your minimum checkpoint ({body.min_affinity_checkpoint})."
        )

    drug_label, protein_label = _generate_display_labels(body.drug_name, body.protein_name, smiles, sequence)
    
    drug_likeness = calculate_drug_likeness(smiles)
    protein_info = compute_protein_info(sequence)

    # Save the prediction results and the exact inputs that produced them.
    # This is useful later for showing history and reproducing the same prediction.
    db = get_database()
    history_record = {
        "user_id": current_user["sub"],
        "drug_smiles": smiles,
        "protein_sequence": sequence,
        "drug_label": drug_label,
        "protein_label": protein_label,
        "affinity": result["affinity"],
        "log_affinity": result["log_affinity"],
        "confidence": result["confidence"],
        "model_name": result["model_name"],
        "metadata": result.get("metadata"),
        "created_at": datetime.now(timezone.utc),
        "drug_likeness": drug_likeness,
        "protein_info": protein_info
    }
    await db["prediction_history"].insert_one(history_record)

    return PredictionResponse(
        **result,
        drug_smiles=smiles,
        protein_sequence=sequence,
        drug_label=drug_label,
        protein_label=protein_label,
        drug_likeness=drug_likeness,
        protein_info=protein_info
    )

@router.post("/predict/batch", response_model=list[PredictionResponse])
@limiter.limit("5/minute")
async def make_batch_prediction(
    request: Request,
    body: BatchPredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Predict interactions for multiple drugs against one protein."""
    if not body.drug_inputs:
        raise HTTPException(status_code=400, detail="Drug inputs are required.")
    if len(body.drug_inputs) > 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch screening is limited to a maximum of 15 drugs to ensure fast response times. You provided {len(body.drug_inputs)}."
        )

    # Check for swapped inputs first
    protein_raw = body.sequence or body.protein_name or ""
    for d_in in (body.drug_inputs or [])[:3]:
        _check_for_swapped_inputs(d_in, protein_raw)

    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    raw_p = (body.sequence or body.protein_name or "").strip().upper()
    
    if not raw_p:
        raise HTTPException(status_code=400, detail="Protein input is required.")
        
    # If the protein input already looks like a real amino acid sequence,
    # use it directly. Otherwise translate the protein name into a sequence.
    if all(c in valid_aa for c in raw_p) and len(raw_p) >= 30:
        sequence = truncate_protein_sequence(raw_p)
    else:
        sequence = await translate_protein_name_to_sequence(raw_p)
        sequence = truncate_protein_sequence(sequence)

    # Validate resolved protein length limit
    _check_resolved_limits(None, sequence)

    p_label = (body.protein_name or "").strip() or f"Sequence ({len(sequence)} aa)"

    valid_smiles = set("CNOPSFIBrclosnpfib0123456789=#@+\\/-[](). ")
    async def resolve_drug(d):
        d = d.strip()
        if not all(c in valid_smiles for c in d):
            resolved = await translate_drug_name_to_smiles(d)
        else:
            resolved = d
        return truncate_drug_smiles(resolved)
        
    resolved_smiles = await asyncio.gather(*(resolve_drug(d) for d in body.drug_inputs), return_exceptions=True)
    
    responses, history = [], []
    p_info = compute_protein_info(sequence)
    
    valid_inputs = []
    valid_smiles_list = []
    for original_input, smiles in zip(body.drug_inputs, resolved_smiles):
        d_label = original_input.strip()[:72]
        if isinstance(smiles, Exception):
            print(f"[Warning] Skipping drug '{d_label}' because it could not be resolved: {smiles}")
            continue
        valid_inputs.append(original_input)
        valid_smiles_list.append(smiles)

    if not valid_smiles_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the provided drug inputs could be resolved. Please check the drug names or input SMILES strings manually."
        )

    # Run batched predictions in parallel on GPU
    try:
        results = await run_in_threadpool(
            predict_dti_batch,
            drug_inputs=valid_smiles_list,
            protein_inputs=[sequence]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    for original_input, smiles, result in zip(valid_inputs, valid_smiles_list, results):
        d_label = original_input.strip()[:72]
        
        # If this result is below the user's quality threshold, do not include it.
        if _is_below_checkpoint(result["log_affinity"], body.min_affinity_checkpoint):
            continue

        d_likeness = calculate_drug_likeness(smiles)
        
        record = {
            "user_id": current_user["sub"],
            "drug_smiles": smiles,
            "protein_sequence": sequence,
            "drug_label": d_label,
            "protein_label": p_label,
            "affinity": result["affinity"],
            "log_affinity": result["log_affinity"],
            "confidence": result["confidence"],
            "model_name": result["model_name"],
            "metadata": result.get("metadata"),
            "created_at": datetime.now(timezone.utc),
            "drug_likeness": d_likeness,
            "protein_info": p_info
        }
        history.append(record)
        responses.append(PredictionResponse(**record))
        
    if not responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the provided drug inputs could be resolved. Please check the drug names or input SMILES strings manually."
        )

    if history:
        await get_database()["prediction_history"].insert_many(history)
        
    return responses

@router.post("/predict/batch-protein", response_model=list[PredictionResponse])
@limiter.limit("5/minute")
async def make_protein_batch_prediction(
    request: Request,
    body: ProteinBatchPredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Predicts interactions for multiple proteins against one drug."""
    if not body.protein_inputs:
        raise HTTPException(status_code=400, detail="Protein inputs are required.")
    if len(body.protein_inputs) > 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch screening is limited to a maximum of 15 proteins to ensure fast response times. You provided {len(body.protein_inputs)}."
        )
    
    # Check for swapped inputs first
    drug_raw = body.smiles or body.drug_name or ""
    for p_in in (body.protein_inputs or [])[:3]:
        _check_for_swapped_inputs(drug_raw, p_in)
    
    if body.smiles and body.smiles.strip():
        smiles = truncate_drug_smiles(body.smiles)
    elif body.drug_name and body.drug_name.strip():
        smiles = await translate_drug_name_to_smiles(body.drug_name.strip())
        smiles = truncate_drug_smiles(smiles)
    else:
        raise HTTPException(status_code=400, detail="Drug input is required.")
        
    d_label = (body.drug_name or "").strip() or smiles[:56] + ("..." if len(smiles) > 56 else "")
    d_likeness = calculate_drug_likeness(smiles)

    # Validate resolved drug length limit
    _check_resolved_limits(smiles, None)

    # Each protein input may be either a name or a sequence, so resolve it individually.
    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    async def resolve_protein(p):
        p = p.strip().upper()
        if not all(c in valid_aa for c in p) or len(p) < 30:
            resolved = await translate_protein_name_to_sequence(p)
        else:
            resolved = p
        return truncate_protein_sequence(resolved)
        
    resolved_sequences = await asyncio.gather(*(resolve_protein(p) for p in body.protein_inputs), return_exceptions=True)
    
    responses, history = [], []
    
    valid_inputs = []
    valid_sequences_list = []
    for original_p, seq in zip(body.protein_inputs, resolved_sequences):
        p_label = original_p.strip()[:72]
        if isinstance(seq, Exception):
            print(f"[Warning] Skipping protein '{p_label}' because it could not be resolved: {seq}")
            continue
        valid_inputs.append(original_p)
        valid_sequences_list.append(seq)

    if not valid_sequences_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the provided protein inputs could be resolved. Please check the protein names or input sequences manually."
        )

    # Run batched predictions in parallel on GPU
    try:
        results = await run_in_threadpool(
            predict_dti_batch,
            drug_inputs=[smiles] * len(valid_sequences_list),
            protein_inputs=valid_sequences_list
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    for original_p, seq, result in zip(valid_inputs, valid_sequences_list, results):
        p_label = original_p.strip()[:72]
        
        # Keep protein-screening output focused on candidates above the checkpoint.
        if _is_below_checkpoint(result["log_affinity"], body.min_affinity_checkpoint):
            continue

        p_info = compute_protein_info(seq)
        
        record = {
            "user_id": current_user["sub"],
            "drug_smiles": smiles,
            "protein_sequence": seq,
            "drug_label": d_label,
            "protein_label": p_label,
            "affinity": result["affinity"],
            "log_affinity": result["log_affinity"],
            "confidence": result["confidence"],
            "model_name": result["model_name"],
            "metadata": result.get("metadata"),
            "created_at": datetime.now(timezone.utc),
            "drug_likeness": d_likeness,
            "protein_info": p_info
        }
        history.append(record)
        responses.append(PredictionResponse(**record))
        
    if not responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="None of the provided protein inputs could be resolved. Please check the protein names or input sequences manually."
        )

    if history:
        await get_database()["prediction_history"].insert_many(history)
        
    return responses
