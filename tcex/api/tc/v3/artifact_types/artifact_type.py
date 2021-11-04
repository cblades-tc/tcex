"""ArtifactType / ArtifactTypes Object"""
# first-party
from tcex.api.tc.v3.api_endpoints import ApiEndpoints
from tcex.api.tc.v3.artifact_types.artifact_type_filter import ArtifactTypeFilter
from tcex.api.tc.v3.artifact_types.artifact_type_model import ArtifactTypeModel, ArtifactTypesModel
from tcex.api.tc.v3.object_abc import ObjectABC
from tcex.api.tc.v3.object_collection_abc import ObjectCollectionABC
from tcex.api.tc.v3.tql.tql_operator import TqlOperator


class ArtifactTypes(ObjectCollectionABC):
    """ArtifactTypes Collection.

    # Example of params input
    {
        'result_limit': 100,  # Limit the retrieved results.
        'result_start': 10,  # Starting count used for pagination.
        'fields': ['caseId', 'summary']  # Select additional return fields.
    }

    Args:
        session (Session): Session object configured with TC API Auth.
        tql_filters (list): List of TQL filters.
        params (dict): Additional query params (see example above).
    """

    def __init__(self, **kwargs) -> None:
        """Initialize class properties."""
        super().__init__(
            kwargs.pop('session', None), kwargs.pop('tql_filter', None), kwargs.pop('params', None)
        )
        self._model = ArtifactTypesModel(**kwargs)
        self._type = 'artifact_types'

    def __iter__(self) -> 'ArtifactType':
        """Iterate over CM objects."""
        return self.iterate(base_class=ArtifactType)

    @property
    def _api_endpoint(self) -> str:
        """Return the type specific API endpoint."""
        return ApiEndpoints.ARTIFACT_TYPES.value

    @property
    def filter(self) -> 'ArtifactTypeFilter':
        """Return the type specific filter object."""
        return ArtifactTypeFilter(self.tql)


class ArtifactType(ObjectABC):
    """ArtifactTypes Object."""

    def __init__(self, **kwargs) -> None:
        """Initialize class properties."""
        super().__init__(kwargs.pop('session', None))
        self._model = ArtifactTypeModel(**kwargs)
        self._type = 'artifact_type'

    @property
    def _api_endpoint(self) -> str:
        """Return the type specific API endpoint."""
        return ApiEndpoints.ARTIFACT_TYPES.value

    @property
    def _base_filter(self) -> dict:
        """Return the default filter."""
        return {
            'keyword': 'artifact_type_id',
            'operator': TqlOperator.EQ,
            'value': self.model.id,
            'type_': 'integer',
        }

    @property
    def as_entity(self) -> dict:
        """Return the entity representation of the object."""
        return {'type': 'ArtifactType', 'id': self.model.id, 'value': self.model.name}