# Pydantic schemas for retrieving past prediction records.

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.drug_target_prediction.prediction_schemas import DrugLikenessInfo, ProteinInfo

class PredictionHistoryRecord(BaseModel):
    """Internal model for storage in MongoDB."""
    user_id: str
    drug_smiles: str
    protein_sequence: str
    drug_label: Optional[str] = ""
    protein_label: Optional[str] = ""
    affinity: float
    log_affinity: float
    confidence: float
    model_name: str
    created_at: datetime
    drug_likeness: Optional[DrugLikenessInfo] = None
    protein_info: Optional[ProteinInfo] = None

class HistoryItemResponse(BaseModel):
    """Single prediction result for the history list view."""
    id: str
    drug_smiles: str
    protein_sequence: str  # Note: Usually truncated in the route for display
    drug_label: Optional[str] = ""
    protein_label: Optional[str] = ""
    affinity: float
    log_affinity: float
    confidence: float
    model_name: str
    created_at: datetime
    drug_likeness: Optional[DrugLikenessInfo] = None
    protein_info: Optional[ProteinInfo] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "drug_label": "Aspirin",
                "protein_label": "EGFR",
                "affinity": 7.45,
                "confidence": 0.85
            }
        }

class HistoryListResponse(BaseModel):
    """Paginated list of history records."""
    total: int
    predictions: List[HistoryItemResponse]
