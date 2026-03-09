import os
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv(".secrets/.env")

class VectorDB:
    def __init__(self):
        api_key = os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY not found in .secrets/.env")
            
        self.pc = Pinecone(api_key=api_key)
        self.index_name = "code-reviewer"
        
        # We handle embeddings ourselves instead of using Chroma's built-in
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Ensure index exists
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=self.encoder.get_sentence_embedding_dimension(),
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-east-1') # Default free tier region
            )
        
        self.index = self.pc.Index(self.index_name)

    def insert(self, tenant_id, documents, metadatas, ids):
        """
        Inserts documents directly into Pinecone using the tenant_id as the Namespace.
        """
        vectors = []
        # Generate embeddings
        embeddings = self.encoder.encode(documents).tolist()
        
        for i in range(len(ids)):
            meta = metadatas[i] if metadatas else {}
            # Pinecone needs the original text saved in metadata to retrieve it
            meta['text'] = documents[i] 
            
            vectors.append({
                "id": str(ids[i]),
                "values": embeddings[i],
                "metadata": meta
            })
            
        # Batch insert into the specific tenant's namespace
        # (Pinecone recommends batches of 100 max, but for MVP we send all at once)
        self.index.upsert(vectors=vectors, namespace=tenant_id)
        
    def query(self, tenant_id, query_texts, n_results=3):
        """
        Queries Pinecone strictly within the tenant_id namespace.
        Matches the return format of ChromaDB for backwards compatibility.
        """
        query_vectors = self.encoder.encode(query_texts).tolist()
        chroma_formatted_results = {
            "documents": [],
            "metadatas": [],
            "ids": []
        }
        
        for q_vec in query_vectors:
            res = self.index.query(
                namespace=tenant_id,
                vector=q_vec,
                top_k=n_results,
                include_metadata=True
            )
            
            docs, metas, ids = [], [], []
            for match in res.matches:
                ids.append(match.id)
                metas.append(match.metadata)
                # Recover original text from metadata
                docs.append(match.metadata.get("text", ""))
                
            chroma_formatted_results["documents"].append(docs)
            chroma_formatted_results["metadatas"].append(metas)
            chroma_formatted_results["ids"].append(ids)
            
        return chroma_formatted_results
