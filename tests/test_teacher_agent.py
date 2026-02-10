import langchain.teacher_agent as teacher_agent


def test_build_khan_style_lesson_deductible_teen():
	lesson = teacher_agent.build_khan_style_lesson(
		module_title="Understanding Deductibles",
		module_description="A comprehensive overview of deductibles.",
		age=16,
	)

	assert "deductible" in lesson.title.lower()
	assert "deductible" in lesson.objective.lower()
	assert any("deductible" in p.lower() for p in lesson.key_points)
	assert "out of your own money" in lesson.worked_example_a.lower()
	assert "deductible" in lesson.recap.lower()


def test_render_lesson_script_contains_sections():
	lesson = teacher_agent.build_khan_style_lesson(
		module_title="What is a claim?",
		module_description="A comprehensive overview of claims.",
		age=18,
	)
	script = teacher_agent.render_lesson_script(lesson)
	assert "Lesson:" in script
	assert "Objective:" in script
	assert "Key points:" in script
	assert "Worked example:" in script
	assert "Recap:" in script


def test_display_module_title_strips_leading_order_prefix():
	assert (
		teacher_agent.display_module_title(27, "27. Understanding rental car coverage")
		== "27. Understanding rental car coverage"
	)
	assert (
		teacher_agent.display_module_title(27, "27) Understanding rental car coverage")
		== "27. Understanding rental car coverage"
	)
	assert (
		teacher_agent.display_module_title(27, "27 - Understanding rental car coverage")
		== "27. Understanding rental car coverage"
	)
