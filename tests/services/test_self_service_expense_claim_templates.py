from pathlib import Path


def test_new_self_service_expense_item_template_has_blank_required_category_option():
    template = Path("/root/dotmac/templates/people/self/expenses.html").read_text()

    assert 'select name="category_id___KEY__"' in template
    assert 'class="form-select w-full" required data-item-category' in template
    assert '<option value="" selected disabled>Select category...</option>' in template


def test_edit_self_service_expense_item_template_has_blank_required_category_option():
    template = Path(
        "/root/dotmac/templates/people/self/expense_claim_edit.html"
    ).read_text()

    assert 'select name="category_id___KEY__"' in template
    assert 'class="form-select w-full" required' in template
    assert '<option value="" selected disabled>Select category...</option>' in template
