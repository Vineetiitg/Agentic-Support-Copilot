from app.graph.workflow import compile_workflow

# Compile your graph
rag_agent = compile_workflow()

# Draw the graph and save it to a file
image_data = rag_agent.get_graph().draw_mermaid_png()

with open("langgraph_architecture.png", "wb") as f:
    f.write(image_data)
    
print("Graph saved as langgraph_architecture.png!")