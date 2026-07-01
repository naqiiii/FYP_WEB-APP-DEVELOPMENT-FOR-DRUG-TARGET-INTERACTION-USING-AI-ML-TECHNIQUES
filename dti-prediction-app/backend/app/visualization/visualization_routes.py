# Handlers for fetching 3D structures from UniProt, AlphaFold, PDB, and PubChem.

import os
import urllib.parse
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.user_authentication.jwt_bearer import get_current_user

def _generate_3d_smiles_rdkit(smiles: str) -> str | None:
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return None
        mol = Chem.AddHs(mol)
        res = AllChem.EmbedMolecule(mol, randomSeed=42)
        if res != 0:
            return None # Embedding failed
        AllChem.MMFFOptimizeMolecule(mol)
        return Chem.MolToMolBlock(mol)
    except Exception as e:
        print(f"RDKit 3D generation failed: {e}")
        return None

router = APIRouter(prefix="/api/visualization", tags=["Visualization"])

# External API base URLs
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_ENTRY = "https://rest.uniprot.org/uniprotkb/{accession}.json"
ALPHAFOLD_PDB = "https://alphafold.ebi.ac.uk/files/AF-{accession}-F1-model_v4.pdb"
ALPHAFOLD_CIF = "https://alphafold.ebi.ac.uk/files/AF-{accession}-F1-model_v4.cif"
RCSB_PDB = "https://files.rcsb.org/download/{pdb_id}.pdb"
ESMFOLD_API = "https://api.esmatlas.com/foldSequence/v1/pdb/"
PUBCHEM_SDF = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{smiles}/SDF"
CACTUS_SDF = "https://cactus.nci.nih.gov/chemical/structure/{smiles}/file?format=sdf&get3d=true"

class ResolveProteinRequest(BaseModel):
    protein_label: str | None = None
    protein_sequence: str | None = None

class ResolveLigandRequest(BaseModel):
    smiles: str

class DockingRequest(BaseModel):
    protein_model_data: str
    protein_format: str = "pdb"
    ligand_model_data: str
    ligand_format: str = "sdf"
    protein_label: str | None = None
    ligand_smiles: str | None = None

async def _get_uniprot_id(client: httpx.AsyncClient, label: str) -> str | None:
    """Find a UniProt accession ID for a given gene or protein name."""
    query = f"(gene_exact:{label} OR protein_name:{label}) AND reviewed:true AND organism_id:9606"
    params = {"query": query, "format": "json", "size": 1}
    resp = await client.get(UNIPROT_SEARCH, params=params, timeout=12.0)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        return results[0].get("primaryAccession") if results else None
    return None

async def _get_alphafold_pdb(client: httpx.AsyncClient, accession: str):
    """Try to fetch a pre-computed structure from AlphaFold DB."""
    for fmt, url_template in [("pdb", ALPHAFOLD_PDB), ("mmcif", ALPHAFOLD_CIF)]:
        resp = await client.get(url_template.format(accession=accession), timeout=20.0)
        if resp.status_code == 200 and resp.text.strip():
            return {"model_data": resp.text, "format": fmt, "source": "alphafold", "accession": accession}
    return None

async def _get_pdb_via_uniprot(client: httpx.AsyncClient, accession: str):
    """Look up experimental PDB structures associated with a UniProt ID."""
    resp = await client.get(UNIPROT_ENTRY.format(accession=accession), timeout=12.0)
    if resp.status_code != 200: return None
    
    pdb_links = [x for x in resp.json().get("uniProtKBCrossReferences", []) if x.get("database") == "PDB"]
    for link in pdb_links[:5]:
        pdb_id = link.get("id")
        if not pdb_id: continue
        pdb_resp = await client.get(RCSB_PDB.format(pdb_id=pdb_id), timeout=20.0)
        if pdb_resp.status_code == 200 and pdb_resp.text.strip():
            return {"model_data": pdb_resp.text, "format": "pdb", "source": "pdb", "accession": accession, "pdb_id": pdb_id}
    return None

async def _predict_structure_esmfold(client: httpx.AsyncClient, sequence: str):
    """Use ESMFold API to predict a structure for a custom amino acid sequence."""
    clean_seq = sequence.replace(" ", "").replace("\n", "").strip()
    if len(clean_seq) < 20: return None
    
    resp = await client.post(ESMFOLD_API, content=clean_seq, headers={"Content-Type": "text/plain"}, timeout=90.0)
    if resp.status_code == 200 and resp.text.strip():
        return {"model_data": resp.text, "format": "pdb", "source": "esmfold"}
    return None

@router.post("/resolve-protein-model")
async def resolve_protein_model(request: ResolveProteinRequest, current_user: dict = Depends(get_current_user)):
    """Convert a protein name or sequence into a 3D structural model."""
    label = (request.protein_label or "").strip()
    seq = (request.protein_sequence or "").strip()

    async with httpx.AsyncClient() as client:
        if label:
            # Try to map a protein name to a UniProt ID, then fetch an existing structure.
            acc = await _get_uniprot_id(client, label)
            if acc:
                model = await _get_alphafold_pdb(client, acc) or await _get_pdb_via_uniprot(client, acc)
                if model: return model
        
        if seq:
            # If no known structure is available, predict one from the raw sequence.
            model = await _predict_structure_esmfold(client, seq)
            if model: return model

    raise HTTPException(status_code=404, detail="Could not find a 3D model for this protein.")

@router.post("/resolve-ligand-model")
async def resolve_ligand_model(request: ResolveLigandRequest, current_user: dict = Depends(get_current_user)):
    """Fetch a 3D SDF structure for a ligand SMILES string."""
    encoded_smiles = urllib.parse.quote(request.smiles.strip(), safe="")
    
    async with httpx.AsyncClient() as client:
        # Try PubChem first because it often has ready-made 3D coordinates.
        resp = await client.get(PUBCHEM_SDF.format(smiles=encoded_smiles), timeout=25.0)
        if resp.status_code == 200 and resp.text.strip():
            return {"model_data": resp.text, "format": "sdf", "source": "pubchem"}

        # Fallback to another public chemical service.
        resp = await client.get(CACTUS_SDF.format(smiles=encoded_smiles), timeout=25.0)
        if resp.status_code == 200 and resp.text.strip():
            return {"model_data": resp.text, "format": "sdf", "source": "cactus"}

    # Final fallback: build a 3D structure in the app itself if the online services fail.
    rdkit_sdf = _generate_3d_smiles_rdkit(request.smiles.strip())
    if rdkit_sdf:
        return {"model_data": rdkit_sdf, "format": "sdf", "source": "rdkit_generated"}

    raise HTTPException(status_code=404, detail="Could not resolve ligand 3D model.")

@router.post("/dock")
async def dock_complex(request: DockingRequest, current_user: dict = Depends(get_current_user)):
    """Forward a docking request to an external specialty provider if configured."""
    provider_url = os.getenv("DOCKING_PROVIDER_URL", "").strip()
    if not provider_url:
        raise HTTPException(
            status_code=501, 
            detail="True docking requires a background provider (DOCKING_PROVIDER_URL not set)."
        )

    payload = {
        "protein_model_data": request.protein_model_data,
        "protein_format": request.protein_format,
        "ligand_model_data": request.ligand_model_data,
        "ligand_format": request.ligand_format,
        "protein_label": request.protein_label,
        "ligand_smiles": request.ligand_smiles,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(provider_url, json=payload, timeout=120.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Docking provider error: {str(e)}")

