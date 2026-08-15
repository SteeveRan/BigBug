"""Pipeline service package.

The former single-module ``app.services.pipeline`` was split into logical
submodules while preserving the original public import surface so that API
routers and tests continue to use ``pipeline_service.<name>`` unchanged.
"""

from app.services.pipeline._clients import (
    _get_client_for_run,
    _get_pipeline_provider_or_404,
    _get_provider_gitlab_client,
)
from app.services.pipeline._components import (
    _check_json_type,
    _get_component_or_404,
    _validate_component_inputs,
    create_component,
    delete_component,
    get_component,
    list_components,
    update_component,
)
from app.services.pipeline._configs import (
    create_pipeline,
    delete_pipeline,
    duplicate_pipeline,
    get_default_pipeline,
    get_pipeline_config,
    get_pipeline_configs,
    restore_pipeline,
    update_pipeline,
)
from app.services.pipeline._runs import (
    cancel_pipeline,
    get_pipeline_run,
    get_pipeline_runs,
    monitor_pipeline_status,
    retry_pipeline,
    trigger_component,
    trigger_pipeline,
    trigger_pipeline_from_config,
    update_pipeline_status,
)
from app.services.pipeline._status import (
    GITLAB_STATUS_MAP,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STATUS_OK,
    STATUS_PENDING,
    STATUS_WARNING,
    _status_text,
)

__all__ = [
    # status
    "STATUS_OK",
    "STATUS_FAILED",
    "STATUS_WARNING",
    "STATUS_IN_PROGRESS",
    "STATUS_PENDING",
    "GITLAB_STATUS_MAP",
    # client helpers
    "_get_provider_gitlab_client",
    "_get_pipeline_provider_or_404",
    "_get_client_for_run",
    # component helpers
    "_get_component_or_404",
    "_validate_component_inputs",
    "_check_json_type",
    "list_components",
    "get_component",
    "create_component",
    "update_component",
    "delete_component",
    # runs
    "trigger_pipeline",
    "trigger_pipeline_from_config",
    "monitor_pipeline_status",
    "cancel_pipeline",
    "retry_pipeline",
    "get_pipeline_runs",
    "get_pipeline_run",
    "update_pipeline_status",
    "trigger_component",
    # configs
    "get_pipeline_configs",
    "get_pipeline_config",
    "create_pipeline",
    "update_pipeline",
    "delete_pipeline",
    "restore_pipeline",
    "duplicate_pipeline",
    "get_default_pipeline",
]
