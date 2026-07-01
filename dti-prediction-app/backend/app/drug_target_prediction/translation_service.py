import httpx
import asyncio
from fastapi import HTTPException, status

# Initialized at module level to reuse connections across requests
_client = httpx.AsyncClient(timeout=60.0)

# Semaphore to limit concurrency (max 5 simultaneous requests to external APIs)
_external_api_semaphore = asyncio.Semaphore(5)

# Simple in-memory cache to avoid redundant network calls for the same drug/protein
_translation_cache = {}

async def translate_drug_name_to_smiles(drug_name: str) -> str:
    """
    Translates a common drug name to its canonical SMILES representation
    using the PubChem PUG REST API.
    """
    cache_key = f"drug:{drug_name.lower().strip()}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/property/CanonicalSMILES/JSON"
    
    async with _external_api_semaphore:
        try:
            response = await _client.get(url)
            # Rate limit enforcement (max 4 req/sec for PubChem)
            await asyncio.sleep(0.25)
            
            if response.status_code == 200:
                data = response.json()
                try:
                    props = data['PropertyTable']['Properties'][0]
                    smiles = None
                    for key, val in props.items():
                        if "SMILES" in key.upper():
                            smiles = val
                            break
                    if smiles:
                        _translation_cache[cache_key] = smiles
                        return smiles
                    raise KeyError("SMILES not found")
                except (KeyError, IndexError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Found drug '{drug_name}' but could not extract SMILES string."
                    )
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not find drug name '{drug_name}' in PubChem. Please provide a SMILES string."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"PubChem server returned error {response.status_code} for '{drug_name}'. "
                        "You can bypass this lookup by entering the canonical SMILES string manually."
                    )
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"We couldn't reach the online PubChem drug database for '{drug_name}' "
                    "due to connection limits or proxy settings on this lab network. "
                    "You can proceed by finding the SMILES chemical formula and pasting it directly into the SMILES input field."
                )
            )

async def translate_protein_name_to_sequence(protein_name: str) -> str:
    """
    Translates a protein name/gene symbol to its FASTA sequence
    using the UniProt REST API. Focuses on human reviewed proteins first.
    """
    cache_key = f"protein:{protein_name.lower().strip()}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    # Search for reviewed (Swiss-Prot) human proteins matching the name
    query = f"(gene_exact:{protein_name} OR protein_name:{protein_name}) AND reviewed:true AND organism_id:9606"
    url = f"https://rest.uniprot.org/uniprotkb/search?query={query}&format=fasta&size=1"
    
    async with _external_api_semaphore:
        try:
            response = await _client.get(url)
            if response.status_code == 200:
                fasta_data = response.text
                if not fasta_data.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Could not find a human protein matching '{protein_name}' in UniProt."
                    )
                
                # Parse FASTA: skip the first header line (starts with >), then join the rest
                lines = fasta_data.strip().split('\n')
                sequence = "".join(line for line in lines if not line.startswith('>'))
                
                _translation_cache[cache_key] = sequence
                return sequence
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"UniProt server returned error {response.status_code} for '{protein_name}'. "
                        "You can bypass this lookup by copying and pasting the raw FASTA sequence manually."
                    )
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"We couldn't reach the online UniProt protein database for '{protein_name}' "
                    "due to connection limits or proxy settings on this lab network. "
                    "You can proceed by copying and pasting the raw amino acid sequence (FASTA format) directly into the sequence input field."
                )
            )
