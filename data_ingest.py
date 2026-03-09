import uuid
from db import VectorDB
from dotenv import load_dotenv

# Load secret API keys from the secure hidden folder
load_dotenv(".secrets/.env")

# Dummy corpus for Tenant A (DeFi Protocol)
TENANT_A_DATA = [
    {
        "bug_id": "TA-001",
        "description": "Reentrancy vulnerability in withdraw function allowing attacker to drain funds before balance decrement.",
        "code": "function withdraw(uint _amount) public {\n    require(balances[msg.sender] >= _amount);\n    (bool sent, ) = msg.sender.call{value: _amount}('');\n    require(sent, 'Failed to send Ether');\n    balances[msg.sender] -= _amount;\n}"
    },
    {
        "bug_id": "TA-002",
        "description": "Missing access control on sensitive admin fee update function.",
        "code": "function setFeeRate(uint256 _rate) public {\n    feeRate = _rate;\n}"
    },
    {
        "bug_id": "TA-003",
        "description": "Flash loan price oracle manipulation risk due to spot price reading.",
        "code": "function getPrice() public view returns (uint256) {\n    return pair.balanceOf(tokenA) / pair.balanceOf(tokenB);\n}"
    },
    {
        "bug_id": "TA-004",
        "description": "Integer underflow leading to infinite token allowance.",
        "code": "function decreaseAllowance(address spender, uint256 amount) public {\n    allowances[msg.sender][spender] -= amount;\n}"
    },
    {
        "bug_id": "TA-005",
        "description": "Unchecked return value from low-level call.",
        "code": "function transferStuckTokens(address to) public {\n    to.call{value: address(this).balance}('');\n}"
    }
]

# Duplicate and vary to have 25 items total for Tenant A
tenant_a_expanded = []
for i in range(5):
    for item in TENANT_A_DATA:
        variant = item.copy()
        variant['bug_id'] = f"{item['bug_id']}-{i}"
        # slight perturbation to make them unique
        variant['description'] = f"Variant {i}: " + item['description']
        tenant_a_expanded.append(variant)

# Dummy corpus for Tenant B (NFT Marketplace)
TENANT_B_DATA = [
    {
        "bug_id": "TB-001",
        "description": "Frontrunning vulnerability in NFT minting allowed bots to snipe drops.",
        "code": "function mint() public payable {\n    require(msg.value == mintPrice);\n    _mint(msg.sender, currentTokenId++);\n}"
    },
    {
        "bug_id": "TB-002",
        "description": "Self-transfer in ERC721 allows bypassing Royalties.",
        "code": "function transferFrom(address from, address to, uint256 tokenId) public {\n    require(ownerOf(tokenId) == from);\n    _transfer(from, to, tokenId);\n}"
    },
    {
        "bug_id": "TB-003",
        "description": "Reentrancy on ERC1155 onERC1155Received hook.",
        "code": "function buyItem(uint256 id) public payable {\n    uint price = listings[id].price;\n    require(msg.value >= price);\n    nft.safeTransferFrom(seller, msg.sender, id, 1, '');\n    payable(seller).transfer(price);\n}"
    },
    {
        "bug_id": "TB-004",
        "description": "Signature replay attack valid across multiple networks due to missing chainId.",
        "code": "function claimWithSig(bytes memory sig) public {\n    bytes32 msgHash = keccak256(abi.encodePacked(msg.sender));\n    address signer = recover(msgHash, sig);\n    require(signer == admin);\n}"
    },
    {
        "bug_id": "TB-005",
        "description": "Strict balance equality check locks contract funds.",
        "code": "function executeSale() public {\n    require(address(this).balance == targetAmount, 'Balance not matched exactly');\n    distributeFunds();\n}"
    }
]

# Duplicate and vary to have 25 items total for Tenant B
tenant_b_expanded = []
for i in range(5):
    for item in TENANT_B_DATA:
        variant = item.copy()
        variant['bug_id'] = f"{item['bug_id']}-{i}"
        variant['description'] = f"Variant {i}: " + item['description']
        tenant_b_expanded.append(variant)


def ingest():
    db = VectorDB()
    
    # Ingest Tenant A
    print("Ingesting Tenant A defaults...")
    docs_a = [item['code'] for item in tenant_a_expanded]
    metas_a = [{"description": item['description'], "bug_id": item['bug_id']} for item in tenant_a_expanded]
    ids_a = [str(uuid.uuid4()) for _ in tenant_a_expanded]
    db.insert("tenant_a", docs_a, metas_a, ids_a)
    
    # Ingest Tenant B
    print("Ingesting Tenant B defaults...")
    docs_b = [item['code'] for item in tenant_b_expanded]
    metas_b = [{"description": item['description'], "bug_id": item['bug_id']} for item in tenant_b_expanded]
    ids_b = [str(uuid.uuid4()) for _ in tenant_b_expanded]
    db.insert("tenant_b", docs_b, metas_b, ids_b)
    
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest()
