from langchain_ollama import ChatOllama

def get_llm():
    llm = ChatOllama(
        model="llama3.2", 
        base_url="http://localhost:11434",
        temperature=0.1,
        num_predict=4000
    )
    return llm