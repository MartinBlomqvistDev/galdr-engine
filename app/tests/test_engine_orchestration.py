import pytest
from galdr.core.engine import GaldrEngine
from galdr.core.nodes import Scenario, NarrativeNode, NodeAction
from galdr.services.mock_service import MockAIService

@pytest.fixture
def mock_scenario():
    return Scenario(
        id="test",
        title="Test Scenario",
        start_node="start",
        nodes={
            "start": NarrativeNode(
                id="start",
                title="Start Node",
                system_prompt="Start prompt",
                actions=[
                    NodeAction(id="go", label="Go", target_node="end")
                ]
            ),
            "end": NarrativeNode(
                id="end",
                title="End Node",
                system_prompt="End prompt"
            )
        }
    )

@pytest.mark.asyncio
async def test_engine_orchestration_loop(mock_scenario):
    # Setup
    ai = MockAIService()
    ai.next_response = "You walk through the door."
    engine = GaldrEngine(mock_scenario, ai, ai)
    
    session = engine.create_session("Tester")
    
    # 1. Test entry
    response = await engine.enter_node(session.session_id)
    assert response.text == "Mock AI response"
    assert "llm_gen" in response.step_latencies
    
    # 2. Test input processing
    response = await engine.process_input(session.session_id, "Gå")
    
    # Verify the 8-step loop results
    assert response.text == "You walk through the door."
    assert session.current_node_id == "end"
    
    # Verify latencies are tracked for all steps
    steps = ["gps_ambient", "intent_match", "mechanics", "transition", "llm_gen", "content_filter", "tts"]
    for step in steps:
        assert step in response.step_latencies
        assert response.step_latencies[step] >= 0
