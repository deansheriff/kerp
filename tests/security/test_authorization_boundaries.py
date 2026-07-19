"""Static regression tests for high-risk authorization boundaries."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _employee_permissions() -> set[str]:
    tree = ast.parse(_source("scripts/seed_rbac.py"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "ROLE_PERMISSIONS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            break
        for key, value in zip(node.value.keys, node.value.values):
            if isinstance(key, ast.Constant) and key.value == "employee":
                assert isinstance(value, ast.List)
                return {
                    item.value
                    for item in value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
    raise AssertionError("employee role permission mapping not found")


def _employee_runtime_scopes() -> set[str]:
    tree = ast.parse(_source("app/services/auth_flow.py"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name)
            and target.id == "EMPLOYEE_SELF_SERVICE_PERMISSIONS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Call) or not node.value.args:
            break
        values = node.value.args[0]
        if not isinstance(values, ast.Set):
            break
        return {
            item.value
            for item in values.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
    raise AssertionError("employee runtime scope baseline not found")


def _role_permissions(role_name: str) -> set[str]:
    tree = ast.parse(_source("scripts/seed_rbac.py"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "ROLE_PERMISSIONS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            break
        for key, value in zip(node.value.keys, node.value.values):
            if isinstance(key, ast.Constant) and key.value == role_name:
                assert isinstance(value, ast.List)
                return {
                    item.value
                    for item in value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                }
    raise AssertionError(f"{role_name} role permission mapping not found")


class EmployeeRoleBoundaryTests(unittest.TestCase):
    def test_employee_role_is_self_service_only(self) -> None:
        permissions = _employee_permissions()
        self.assertIn("self:access", permissions)
        self.assertIn("hr:employees:directory", permissions)
        self.assertNotIn("hr:employees:read", permissions)
        self.assertNotIn("hr:access", permissions)
        self.assertNotIn("hr:employees:read_sensitive", permissions)
        self.assertNotIn("hr:employees:create", permissions)
        self.assertNotIn("hr:employees:update", permissions)
        self.assertNotIn("hr:employees:delete", permissions)
        self.assertNotIn("expense:access", permissions)
        self.assertNotIn("projects:access", permissions)
        self.assertNotIn("support:access", permissions)

    def test_startup_seed_reconciles_employee_role_exactly(self) -> None:
        source = _source("scripts/seed_admin.py")
        self.assertIn('ROLE_PERMISSIONS["employee"]', source)
        self.assertIn("RolePermission.permission_id.notin_", source)
        self.assertNotIn("legacy_employee_grants", source)

    def test_startup_seed_deduplicates_role_permissions_before_flush(self) -> None:
        source = _source("scripts/seed_admin.py")
        self.assertIn("known_role_permission_pairs = {", source)
        self.assertGreaterEqual(source.count("known_role_permission_pairs,"), 2)
        self.assertIn("if known_pairs is not None and pair in known_pairs", source)

    def test_runtime_employee_scope_baseline_matches_seed(self) -> None:
        self.assertEqual(_employee_permissions(), _employee_runtime_scopes())

    def test_tighter_routes_keep_expected_manager_access(self) -> None:
        operations_permissions = _role_permissions("operations_manager")
        finance_permissions = _role_permissions("finance_manager")
        self.assertIn("inventory:items:read", operations_permissions)
        self.assertIn("inventory:transactions:adjust", operations_permissions)
        self.assertIn("gl:balances:read", finance_permissions)


class RouteBoundaryTests(unittest.TestCase):
    def assert_guard(self, path: str, function: str, guard: str) -> None:
        source = _source(path)
        start = source.index(f"def {function}(")
        end = source.find("\n\ndef ", start + 1)
        async_end = source.find("\n\nasync def ", start + 1)
        candidates = [value for value in (end, async_end) if value != -1]
        block = source[start : min(candidates) if candidates else len(source)]
        self.assertIn(f"Depends({guard})", block)

    def test_employee_management_routes_are_granular(self) -> None:
        source = _source("app/web/people/hr/employees.py")
        self.assertNotIn("require_hr_access", source)
        self.assert_guard(
            "app/web/people/hr/employees.py", "create_employee", "_employee_create"
        )
        self.assert_guard(
            "app/web/people/hr/employees.py",
            "resend_employee_invite",
            "_employee_credentials",
        )

    def test_employee_login_management_uses_specific_permission(self) -> None:
        source = _source("app/web/people/hr/lifecycle.py")
        self.assertIn(
            '_employee_credentials = require_web_permission('
            '"hr:employees:manage_credentials")',
            source,
        )
        self.assert_guard(
            "app/web/people/hr/lifecycle.py",
            "create_employee_user_credentials",
            "_employee_credentials",
        )
        self.assert_guard(
            "app/web/people/hr/lifecycle.py",
            "link_employee_user",
            "_employee_credentials",
        )
        self.assert_guard(
            "app/web/people/hr/lifecycle.py",
            "search_people",
            "_employee_credentials",
        )

    def test_employee_login_controls_follow_credential_permission(self) -> None:
        service = _source("app/services/people/hr/web/employee_web.py")
        detail = _source("templates/people/hr/employee_detail.html")
        directory = _source(
            "templates/people/hr/employee_directory_detail.html"
        )
        self.assertIn('"can_manage_credentials": can_manage_credentials', service)
        self.assertIn("credential.provider == AuthProvider.local", service)
        self.assertIn("{% if can_manage_credentials %}", detail)
        self.assertIn("{% if can_manage_credentials %}", directory)
        self.assertIn("{% if has_local_credential %}disabled{% endif %}", detail)

    def test_people_landing_supports_read_only_employee_access(self) -> None:
        source = _source("app/web/people/dashboard.py")
        self.assertIn("Depends(require_web_auth)", source)
        self.assertIn(") -> Response:", source)
        self.assertNotIn("HTMLResponse | RedirectResponse", source)
        self.assertIn('auth.has_permission("hr:dashboard")', source)
        self.assertIn('"hr:employees:directory", "hr:employees:read"', source)
        self.assertIn('url="/people/hr/employees"', source)

    def test_directory_detail_does_not_render_sensitive_hr_record(self) -> None:
        service = _source("app/services/people/hr/web/employee_web.py")
        directory_template = _source(
            "templates/people/hr/employee_directory_detail.html"
        )
        self.assertIn('auth.has_permission("hr:employees:read_sensitive")', service)
        self.assertIn("Work information", directory_template)
        self.assertNotIn("salary", directory_template.lower())
        self.assertNotIn("tax", directory_template.lower())
        self.assertIn("{% if can_manage_credentials %}", directory_template)

    def test_broad_hr_gate_ignores_employee_role_grants(self) -> None:
        source = _source("app/web/deps.py")
        self.assertIn("def _has_non_employee_hr_access", source)
        self.assertIn('func.lower(Role.name) != "employee"', source)
        self.assertIn("not has_valid_hr_role", source)

    def test_web_sessions_reload_current_effective_permissions(self) -> None:
        source = _source("app/web/deps.py")
        self.assertGreaterEqual(source.count("load_effective_rbac_claims("), 2)
        self.assertNotIn("_load_web_permission_scopes", source)

    def test_api_sessions_reload_current_effective_permissions(self) -> None:
        source = _source("app/services/auth_dependencies.py")
        self.assertGreaterEqual(source.count("load_effective_rbac_claims("), 4)
        self.assertNotIn("select(RolePermission)", source)

    def test_employee_role_is_filtered_at_permission_query(self) -> None:
        source = _source("app/services/auth_flow.py")
        self.assertIn('func.lower(Role.name) != "employee"', source)
        self.assertIn(
            "Permission.key.in_(EMPLOYEE_SELF_SERVICE_PERMISSIONS)", source
        )

    def test_employee_create_is_guarded_on_web_and_api(self) -> None:
        web_source = _source("app/web/people/hr/employees.py")
        api_source = _source("app/api/people/hr.py")
        self.assertIn(
            '_employee_create = require_web_permission("hr:employees:create")',
            web_source,
        )
        self.assertIn(
            'require_tenant_permission("hr:employees:create")', api_source
        )

    def test_employee_directory_permission_does_not_open_employee_api(self) -> None:
        permissions = _employee_permissions()
        api_source = _source("app/api/people/hr.py")
        self.assertIn("hr:employees:directory", permissions)
        self.assertNotIn("hr:employees:read", permissions)
        self.assertIn(
            'require_tenant_permission("hr:employees:read")', api_source
        )
        self.assertNotIn("hr:employees:directory", api_source)

    def test_health_exposes_authorization_policy_version(self) -> None:
        source = _source("app/main.py")
        self.assertIn('"authorization_policy": "effective-rbac-v2"', source)

    def test_integration_and_scheduler_apis_have_permission_boundaries(self) -> None:
        self.assertIn(
            'require_tenant_permission("integrations:manage")',
            _source("app/api/service_hooks.py"),
        )
        self.assertIn(
            'require_tenant_permission("integrations:manage")',
            _source("app/api/crm.py"),
        )
        scheduler = _source("app/api/scheduler.py")
        self.assertIn("require_tenant_method_permission", scheduler)
        self.assertIn('"scheduler:read", "scheduler:manage"', scheduler)

    def test_finance_import_and_analysis_apis_have_specific_guards(self) -> None:
        opening_balance = _source("app/api/finance/opening_balance.py")
        analysis = _source("app/api/finance/analysis.py")
        self.assertIn(
            'require_tenant_permission("gl:balances:read")', opening_balance
        )
        self.assertGreaterEqual(
            opening_balance.count(
                'require_tenant_permission("gl:journals:create")'
            ),
            2,
        )
        self.assertIn('"gl:accounts:create" not in scopes', opening_balance)
        self.assertIn('require_tenant_permission("gl:balances:read")', analysis)

    def test_fleet_write_access_is_separate_from_module_access(self) -> None:
        source = _source("app/api/fleet/__init__.py")
        self.assertIn('require_tenant_permission("fleet:access")', source)
        self.assertIn(
            'require_tenant_method_permission("fleet:read", "fleet:manage")',
            source,
        )

    def test_workflow_task_mutations_require_scope_and_assignment(self) -> None:
        source = _source("app/api/workflow_tasks.py")
        self.assertIn("def _require_assigned_task", source)
        self.assertIn("task.assignee_employee_id != employee_id", source)
        self.assertIn('require_tenant_permission("tasks:update")', source)
        self.assertIn('require_tenant_permission("tasks:complete")', source)

    def test_support_and_project_routes_do_not_use_module_wide_guards(self) -> None:
        self.assertNotIn("require_support_access", _source("app/web/support.py"))
        self.assertNotIn("require_projects_access", _source("app/web/projects.py"))

    def test_financial_workflow_actions_have_specific_guards(self) -> None:
        self.assert_guard("app/web/finance/gl.py", "post_journal", "_journals_post")
        self.assert_guard(
            "app/web/finance/ar.py", "approve_invoice", "_invoices_post"
        )
        self.assert_guard(
            "app/web/finance/banking.py",
            "reconciliation_approve",
            "_reconciliation_approve",
        )

    def test_finance_read_routes_do_not_use_module_wide_guards(self) -> None:
        for path in (
            "app/web/finance/gl.py",
            "app/web/finance/ar.py",
            "app/web/finance/banking.py",
        ):
            self.assertNotIn("require_finance_access", _source(path))

    def test_expense_records_apply_employee_scope(self) -> None:
        routes = _source("app/web/finance/exp.py")
        claims = _source("app/services/expense/web_claims.py")
        advances = _source("app/services/expense/web_advances.py")
        self.assertNotIn("require_expense_access", routes)
        self.assertIn("readable_employee_ids(", claims)
        self.assertIn("_can_read_claim", claims)
        self.assertIn("_owned_claim", claims)
        self.assertIn("can_read_employee_record(", advances)

    def test_inventory_and_fixed_asset_mutations_are_granular(self) -> None:
        self.assert_guard(
            "app/web/inventory.py",
            "create_transfer_transaction",
            "_transactions_transfer",
        )
        self.assert_guard(
            "app/web/fixed_assets.py", "dispose_asset", "_fa_assets_dispose"
        )
        self.assert_guard(
            "app/web/fixed_assets.py",
            "post_depreciation_run",
            "_fa_depreciation_post",
        )

    def test_inventory_and_fixed_asset_reads_are_granular(self) -> None:
        self.assert_guard("app/web/inventory.py", "list_items", "_items_read")
        self.assert_guard(
            "app/web/inventory.py",
            "inventory_valuation_report",
            "_valuation_read",
        )
        self.assertNotIn(
            "require_fixed_assets_access", _source("app/web/fixed_assets.py")
        )


if __name__ == "__main__":
    unittest.main()
