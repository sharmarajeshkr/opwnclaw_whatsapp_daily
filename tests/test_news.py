import pytest
import re
from app.agents.news_agent import NewsAgent

@pytest.fixture
def news_agent():
    return NewsAgent("919876543210")

@pytest.mark.anyio
async def test_news_agent_uses_provided_data(news_agent):
    # Mock data that would come from MCP
    source_data = (
        "Found 2 news items:\n"
        "1. Real SAP Migration Guide - TechCorp\n"
        "   Link: https://real-domain.com/sap-guide\n"
        "2. S/4HANA Case Study - BizBlog\n"
        "   Link: https://bizblog.io/s4-case-study\n"
    )
    
    prompt = f"I pulled this data:\n{source_data}\nRewrite it for WhatsApp. use exact links."
    
    # We call the real LLM (or it uses the configured provider)
    # For a unit test, we'd ideally mock the LLMProvider, but let's verify integration
    # unless we want a pure logic test.
    content = await news_agent.get_curated_content("Tech_news", prompt)
    
    # 1. Verify placeholder links are NOT present
    assert "example.com" not in content.lower()
    
    # 2. Verify real links FROM THE DATA are present
    # We check for the domain names at least
    assert "real-domain.com" in content.lower()
    assert "bizblog.io" in content.lower()
    
    # 3. Verify structure and content relevance
    assert any(x in content.lower() for x in ["sap", "migration", "s/4hana"])
    assert len(content) > 100 # Ensure it's not empty or too short

@pytest.mark.anyio
async def test_news_agent_fallback_mode(news_agent):
    # Test how it handles a generic prompt without data (legacy fallback)
    # We want to ensure it still produces SOMETHING even if links might be fake here
    # but our prompt in scheduler.py now tries to avoid this.
    prompt = "Top global news about AI for today."
    content = await news_agent.get_curated_content("Tech_news", prompt)
    
    assert len(content) > 50
    assert "AI" in content
