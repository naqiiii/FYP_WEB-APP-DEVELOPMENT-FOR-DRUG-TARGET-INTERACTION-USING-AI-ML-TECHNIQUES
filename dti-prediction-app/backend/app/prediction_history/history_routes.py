from fastapi import APIRouter, Depends, Query
from app.mongodb_connection import get_database
from app.user_authentication.jwt_bearer import get_current_user
from app.prediction_history.history_schemas import HistoryItemResponse, HistoryListResponse

router = APIRouter(prefix="/api", tags=["Prediction History"])

@router.get("/history", response_model=HistoryListResponse)
async def get_prediction_history(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0)
):
    """Retrieve the logged-in user's prediction history with pagination."""
    db = get_database()
    user_id = current_user["sub"]
    
    # Keep the count separate so pagination stays accurate.
    total = await db["prediction_history"].count_documents({"user_id": user_id})
    
    cursor = db["prediction_history"].find({"user_id": user_id}) \
                                     .sort("created_at", -1) \
                                     .skip(skip) \
                                     .limit(limit)
    
    predictions = []
    async for record in cursor:
        # Long protein sequences make the history table hard to scan.
        seq = record["protein_sequence"]
        display_seq = seq if len(seq) <= 50 else f"{seq[:50]}..."
        
        predictions.append(HistoryItemResponse(
            id=str(record["_id"]),
            drug_smiles=record["drug_smiles"],
            protein_sequence=display_seq,
            drug_label=record.get("drug_label", ""),
            protein_label=record.get("protein_label", ""),
            affinity=record["affinity"],
            log_affinity=record["log_affinity"],
            confidence=record["confidence"],
            model_name=record["model_name"],
            created_at=record["created_at"],
            drug_likeness=record.get("drug_likeness"),
            protein_info=record.get("protein_info")
        ))
    
    return HistoryListResponse(total=total, predictions=predictions)
