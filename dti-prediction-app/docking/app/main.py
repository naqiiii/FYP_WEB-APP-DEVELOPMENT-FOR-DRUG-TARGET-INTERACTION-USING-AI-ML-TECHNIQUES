from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any
import os


class DockRequest(BaseModel):
    protein_model_data: str = Field(..., min_length=1)
    protein_format: str = Field(default="pdb")
    ligand_model_data: str = Field(..., min_length=1)
    ligand_format: str = Field(default="sdf")
    protein_label: str | None = None
    ligand_smiles: str | None = None


class DockResponse(BaseModel):
    protein_model_data: str
    protein_format: str
    ligand_pose_data: str
    ligand_format: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(
    title="DTI Docking Service",
    version="0.1.0",
    description=(
        "Local docking microservice contract for DTI backend.\n\n"
        "Default mode returns a mock pose (pass-through ligand data) so the pipeline works end-to-end.\n"
        "Replace `run_real_docking` with your AutoDock Vina/GNINA integration."
    ),
)


def run_mock_docking(request: DockRequest) -> DockResponse:
    # This is a fake docking response so the rest of the app can still work.
    # In other words, the frontend can show a docking pose even when docking is not set up.
    target = request.protein_label or "target protein"
    return DockResponse(
        protein_model_data=request.protein_model_data,
        protein_format=request.protein_format,
        ligand_pose_data=request.ligand_model_data,
        ligand_format=request.ligand_format,
        score=-7.0,
        metadata={
            "provider": "mock",
            "note": "No physical docking executed. Integrate Vina in run_real_docking().",
            "protein_label": request.protein_label,
            "beginner_message": (
                f"The drug appears to fit reasonably in the binding region of {target} in this mock pose, "
                "which is consistent with a moderate-to-good interaction signal."
            ),
            "expert_message": (
                "Mock docking score suggests a plausible pose, but interaction-level evidence is synthetic. "
                "Use real docking + rescoring before medicinal chemistry decisions."
            ),
            "interaction_reasons": [
                "Ligand geometry is compatible with a pocket-sized cavity.",
                "Pose suggests mixed hydrophobic and polar contacts.",
                "No severe steric clash is assumed in the generated mock arrangement.",
            ],
            "caveats": [
                "This is a template/mock pose, not an engine-computed Vina/GNINA pose.",
                "Contact patterns are heuristic and should not be interpreted as validated residue interactions.",
            ],
        },
    )


def run_real_docking(request: DockRequest) -> DockResponse:
    # Place your real docking engine call here, for example AutoDock Vina or GNINA.
    raise NotImplementedError("Real docking engine is not implemented yet.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/dock", response_model=DockResponse)
async def dock(request: DockRequest) -> DockResponse:
    # Choose whether to return a fake docking pose or to use a real docking engine.
    mode = os.getenv("DOCKING_MODE", "mock").strip().lower()

    if mode == "mock":
        return run_mock_docking(request)
    if mode == "real":
        # This branch is ready for Vina/GNINA integration without changing the API contract.
        try:
            return run_real_docking(request)
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Docking failed: {exc}")

    raise HTTPException(status_code=400, detail=f"Unsupported DOCKING_MODE '{mode}'. Use 'mock' or 'real'.")

