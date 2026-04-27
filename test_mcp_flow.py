import pandas as pd
import base64
import asyncio
import json

from mcp_server import call_tool

# 1. Create dummy unstructured data
df = pd.DataFrame({
    "Creative Concept": ["Pixel Pro Video", "Pixel Standard Static"],
    "Where it ran": ["TikTok", "Meta"],
    "The Objective": ["Video Views", "Awareness"],
    "Total Spent (€)": [1500, 800],
    "Impressions Total": [100000, 50000],
    "People Reached": [80000, 45000],
    "Link Clicks": [500, 100],
    "3s Video Plays": [20000, 0],
    "100% Video Completions": [1000, 0],
    "Buying Method": ["Paid", "Paid"],
    "Format Type": ["Video", "Static"]
})

df.to_excel("dummy_unstructured.xlsx", index=False)

# 2. Base64 encode it
with open("dummy_unstructured.xlsx", "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("utf-8")

# 3. Call the MCP tool
async def test_mcp():
    print("Calling analyze_creatives...")
    response = await call_tool("analyze_creatives", {
        "file_data_base64": b64_data,
        "file_name": "dummy_unstructured.xlsx"
    })
    
    print("\n--- MCP Server Response ---")
    for content in response:
        print(content.text)
        
    # Check if the output actually mapped correctly
    # If LLM mapping failed, the spend/reach will likely be 0
    try:
        data = json.loads(response[0].text)
        for p in data.get("top_performers", []):
            print(f"\nCreative: {p['creative_name']} - Spend: {p['spend']} - Score: {p['score']}")
    except Exception as e:
        print("Could not parse JSON response")

if __name__ == "__main__":
    asyncio.run(test_mcp())
