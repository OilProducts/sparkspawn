from attractor.dsl import parse_dot
from attractor.transforms import GoalVariableTransform, ModelStylesheetTransform, TransformPipeline


class TestTransforms:
    def test_goal_variable_transform(self):
        graph = parse_dot(
            """
            digraph G {
                graph [goal="Build API"]
                start [shape=Mdiamond]
                plan [shape=box, prompt="Plan for $goal"]
                done [shape=Msquare]
                start -> plan -> done
            }
            """
        )

        GoalVariableTransform().apply(graph)
        assert graph.nodes["plan"].attrs["prompt"].value == "Plan for Build API"

    def test_stylesheet_specificity_and_explicit_override(self):
        graph = parse_dot(
            """
            digraph G {
                graph [model_stylesheet="* { llm_model: base; llm_provider: generic; } .fast { llm_model: flash; } #review { llm_model: best; llm_provider: openai; reasoning_effort: high; }"]

                start [shape=Mdiamond]
                plan [shape=box, class="fast"]
                review [shape=box, class="fast", llm_model="explicit"]
                done [shape=Msquare]
                start -> plan -> review -> done
            }
            """
        )

        ModelStylesheetTransform().apply(graph)

        # class overrides shape and universal
        assert graph.nodes["plan"].attrs["llm_model"].value == "flash"
        # explicit attribute is not overwritten
        assert graph.nodes["review"].attrs["llm_model"].value == "explicit"
        # other properties from highest-specific rule can still apply
        assert graph.nodes["review"].attrs["llm_provider"].value == "openai"
        assert graph.nodes["review"].attrs["reasoning_effort"].value == "high"

    def test_transform_pipeline_order(self):
        graph = parse_dot(
            """
            digraph G {
                graph [goal="Landing Page", model_stylesheet="* { llm_model: gpt-5; }"]
                start [shape=Mdiamond]
                task [shape=box, prompt="Build $goal"]
                done [shape=Msquare]
                start -> task -> done
            }
            """
        )

        pipeline = TransformPipeline()
        pipeline.register(GoalVariableTransform())
        pipeline.register(ModelStylesheetTransform())
        pipeline.apply(graph)

        assert graph.nodes["task"].attrs["prompt"].value == "Build Landing Page"
        assert graph.nodes["task"].attrs["llm_model"].value == "gpt-5"
