# Prediction Data Models
# Pydantic schemas for DTI prediction requests and responses.
# These classes describe the shape of the data the API expects and returns.

from typing import Optional
from pydantic import BaseModel, Field

# --- Request Schemas ---

class PredictionRequest(BaseModel):
    """Input for a single Drug-Target Interaction prediction."""
    drug_name: Optional[str] = Field("", description="Drug name (e.g. 'Imatinib')")
    smiles: Optional[str] = Field("", max_length=1000, description="SMILES string")
    protein_name: Optional[str] = Field("", description="Protein name (e.g. 'ABL1')")
    sequence: Optional[str] = Field("", max_length=2048, description="Amino acid sequence")
    min_affinity_checkpoint: Optional[float] = Field(None, description="Minimum affinity (pKd) to include in results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "drug_name": "Imatinib",
                "protein_name": "ABL1"
            }
        }

class BatchPredictionRequest(BaseModel):
    """Screen multiple drugs against a single protein target."""
    drug_inputs: list[str] = Field(..., min_length=1, max_length=15, description="List of drug names or SMILES")
    protein_name: Optional[str] = Field("", description="Target protein name")
    sequence: Optional[str] = Field("", max_length=2048, description="Target sequence")
    min_affinity_checkpoint: Optional[float] = Field(None, description="Minimum affinity (pKd) to include in results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "drug_inputs": ["Imatinib", "Aspirin"],
                "protein_name": "ABL1"
            }
        }

class ProteinBatchPredictionRequest(BaseModel):
    """Screen a single drug against multiple protein targets."""
    drug_name: Optional[str] = Field("", description="Drug name")
    smiles: Optional[str] = Field("", max_length=1000, description="Drug SMILES")
    protein_inputs: list[str] = Field(..., min_length=1, max_length=15, description="List of protein names or sequences")
    min_affinity_checkpoint: Optional[float] = Field(None, description="Minimum affinity (pKd) to include in results")

# --- Supporting Models ---

class DrugLikenessInfo(BaseModel):
    """Calculated molecular properties and drug-likeness rules."""
    mw: float
    logp: float
    hba: int
    hbd: int
    tpsa: float
    rotatable_bonds: int
    lipinski_violations: int
    lipinski_pass: bool
    veber_pass: bool
    label: str  # e.g., 'good', 'moderate', 'poor'

class ProteinInfo(BaseModel):
    """Basic biological information about a protein sequence."""
    length: int
    organism: str = ""
    protein_class: str = ""

class ModelMetadata(BaseModel):
    """Metadata for interpreting the model's output in the UI."""
    threshold_strong: float = 7.0
    threshold_moderate: float = 6.0
    gauge_min: float = 3.0
    gauge_max: float = 9.0
    unit: str = "pKd"

# --- Response Schemas ---

class PredictionResponse(BaseModel):
    """Output from the DTI prediction model including input confirmation and analysis."""
    status: str = Field("SUCCESS", description="SUCCESS or ERROR")
    error_message: Optional[str] = Field(None, description="Error details if status is ERROR")
    affinity: Optional[float] = Field(None, description="Predicted Kd/binding affinity")
    log_affinity: Optional[float] = Field(None, description="Log-transformed pKd")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Model confidence (0-1)")
    model_name: str = Field(..., description="Name of the used model")
    
    # Echoed inputs and labels
    drug_smiles: str
    protein_sequence: str
    drug_label: str = ""
    protein_label: str = ""
    
    # Detailed analysis
    drug_likeness: Optional[DrugLikenessInfo] = None
    protein_info: Optional[ProteinInfo] = None
    metadata: Optional[ModelMetadata] = None

    class Config:
        json_schema_extra = {
            "example": {
                "affinity": 7.45,
                "confidence": 0.85,
                "drug_label": "Imatinib",
                "protein_label": "ABL1"
            }
        }
