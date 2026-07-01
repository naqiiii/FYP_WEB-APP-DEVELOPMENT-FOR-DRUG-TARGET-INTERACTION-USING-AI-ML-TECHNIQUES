import logging

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem import Crippen
    from rdkit.Chem import Lipinski
    RDKIT_AVAILABLE = True
except ImportError:
    logging.warning("RDKit is not installed; molecular properties will return None.")
    RDKIT_AVAILABLE = False


def calculate_drug_likeness(smiles: str) -> dict | None:
    """
    Computes chemical descriptors and applies Lipinski/Veber rules.
    Returns None if RDKit is not installed or SMILES parsing fails.
    """
    if not RDKIT_AVAILABLE or not smiles:
        return None

    try:
        mol = Chem.MolFromSmiles(smiles.strip())
        if mol is None:
            return None

        # 1. Compute Descriptors
        mw = Descriptors.MolWt(mol)
        logp = Crippen.MolLogP(mol)
        hba = Lipinski.NumHAcceptors(mol)
        hbd = Lipinski.NumHDonors(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)

        # 2. Rule Violations (Lipinski Rule of Five)
        lipinski_violations = 0
        if mw > 500: lipinski_violations += 1
        if logp > 5: lipinski_violations += 1
        if hba > 10: lipinski_violations += 1
        if hbd > 5: lipinski_violations += 1
        lipinski_pass = (lipinski_violations == 0)

        # 3. Rule Violations (Veber Rules)
        veber_violations = 0
        if tpsa > 140: veber_violations += 1
        if rot_bonds > 10: veber_violations += 1
        veber_pass = (veber_violations == 0)

        # 4. Categorical Label Output
        total_violations = lipinski_violations + veber_violations
        if total_violations == 0:
            label = "good"
        elif total_violations == 1:
            label = "moderate"
        else:
            label = "poor"

        return {
            "mw": round(mw, 2),
            "logp": round(logp, 2),
            "hba": hba,
            "hbd": hbd,
            "tpsa": round(tpsa, 2),
            "rotatable_bonds": rot_bonds,
            "lipinski_violations": lipinski_violations,
            "lipinski_pass": lipinski_pass,
            "veber_pass": veber_pass,
            "label": label
        }

    except Exception as e:
        logging.error(f"Error computing drug likeness for {smiles}: {str(e)}")
        return None


def compute_protein_info(sequence: str) -> dict | None:
    """
    Calculates biological descriptors safely.
    Intentionally does not hallucinate organisms/classes.
    """
    if not sequence:
        return None
        
    seq = sequence.replace(" ", "").replace("\n", "").strip()
    return {
        "length": len(seq),
        "organism": "Unknown (Local DB)",
        "protein_class": "Target Sequence"
    }
