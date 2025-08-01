"""TcEx Framework Module"""

# standard library
from datetime import datetime

# first-party
from tcex.api.tc.ti_transform.model import GroupTransformModel, IndicatorTransformModel
from tcex.api.tc.ti_transform.transform_abc import (
    NoValidTransformException,
    TransformABC,
    TransformException,
    TransformsABC,
)


class TiTransforms(TransformsABC):
    """Mappings"""

    def process(self):
        """Process the mapping."""
        self.transformed_collection: list[TiTransform] = []
        for ti_dict in self.ti_dicts:
            self.transformed_collection.append(
                TiTransform(
                    ti_dict,
                    self.transforms,
                    seperate_batch_associations=self.seperate_batch_associations,
                )
            )

    @property
    def batch(self) -> dict:
        """Return the data in batch format."""
        self.process()

        batch = {
            'group': [],
            'indicator': [],
        }
        self.log.trace(f'feature=ti-transform-batch, ti-count={len(self.transformed_collection)}')
        for index, t in enumerate(self.transformed_collection):
            if index and index % 1_000 == 0:
                self.log.trace(f'feature=ti-transform-batch, items={index}')

            # batch must be called so that the transform type is selected
            try:
                data = t.batch
            except NoValidTransformException:
                self.log.exception('feature=ti-transforms, event=runtime-error')
                continue
            except TransformException as e:
                self.log.warning(
                    f'feature=ti-transforms, event=transform-error, field="{e.field}", '
                    f'cause="{e.cause}", context="{e.context}"'
                )
                if self.raise_exceptions:
                    raise
                continue
            except Exception:
                self.log.exception('feature=ti-transforms, event=transform-error')
                if self.raise_exceptions:
                    raise
                continue

            # now that batch is called we can identify the ti type
            if self.seperate_batch_associations:
                associations = data.pop('association', [])
                batch.setdefault('association', []).extend(associations)
            if isinstance(t.transform, GroupTransformModel):
                batch['group'].append(data)
            elif isinstance(t.transform, IndicatorTransformModel):
                batch['indicator'].append(data)

            # append adhoc groups and indicators
            batch['group'].extend(t.adhoc_groups)
            batch['indicator'].extend(t.adhoc_indicators)
        return batch

    @property
    def v3_api(self) -> dict:
        """Return the data in v3 format."""
        self.process()

        v3_data = {}
        self.log.trace(f'feature=ti-transform-v3, ti-count={len(self.transformed_collection)}')
        for index, t in enumerate(self.transformed_collection):
            if index and index % 1_000 == 0:
                self.log.trace(f'feature=ti-transform-v3, items={index}')

            # v3_api must be called so that the transform type is selected
            try:
                data = t.v3_api
            except NoValidTransformException:
                self.log.exception('feature=ti-transforms, event=runtime-error')
                continue
            except TransformException as e:
                self.log.warning(
                    f'feature=ti-transforms, event=transform-error, field="{e.field}", '
                    f'cause="{e.cause}", context="{e.context}"'
                )
                if self.raise_exceptions:
                    raise
                continue
            except Exception:
                self.log.exception('feature=ti-transforms, event=transform-error')
                if self.raise_exceptions:
                    raise
                continue

            v3_data.setdefault(data.pop('type'), []).extend(data)

        return v3_data


class TiTransform(TransformABC):
    """Threat Intelligence Transform Module"""

    def add_custom_association(self, summary: str, indicator_type: str, association_type: str):
        """Add a custom association."""
        if not self.seperate_batch_associations:
            raise TransformException(
                field='associatedIndicator',
                cause=RuntimeError(
                    'Cannot add associated indicator to IndicatorTransformModel when '
                    'seperate_batch_associations is False.'
                ),
                context=self.transformed_item,
            )

        self.transformed_item.setdefault('association', []).append(
            {
                'ref_1': self.transformed_item['summary'],
                'type_1': self.transformed_item['type'],
                'ref_2': summary,
                'type_2': indicator_type,
                'association_type': association_type,
            }
        )

    def add_associated_indicator(self, summary: str, indicator_type: str):
        """Add an associated indicator."""
        if not self.seperate_batch_associations:
            self.transformed_item.setdefault('associatedIndicators', []).append(
                {'summary': summary, 'indicatorType': indicator_type}
            )
        else:
            self.transformed_item.setdefault('association', []).append(
                {
                    'ref_1': self.transformed_item['xid'],
                    'ref_2': summary,
                    'type_2': indicator_type,
                }
            )

    def add_associated_group(self, group_xid: str):
        """Add an associated group.

        {
            'associatedGroups': [
                {
                    'groupXid': 'dd78f2b94ac61d3e5a55c1223a7635db00cd0aaa8aba26c5306e36dd6c1662ee'}
        """
        if not self.seperate_batch_associations:
            # process type specific data
            if isinstance(self.transform, GroupTransformModel):
                self.transformed_item.setdefault('associatedGroupXid', []).append(group_xid)
            elif isinstance(self.transform, IndicatorTransformModel):
                associated_group = {'groupXid': group_xid}
                self.transformed_item.setdefault('associatedGroups', []).append(associated_group)
        elif isinstance(self.transform, GroupTransformModel):
            self.transformed_item.setdefault('association', []).append(
                {
                    'ref_1': group_xid,
                    'ref_2': self.transformed_item['xid'],
                }
            )
            self.log.info(
                'Added associated group with xid: %s to %s',
                group_xid,
                self.transformed_item['xid'],
            )
        elif isinstance(self.transform, IndicatorTransformModel):
            self.transformed_item.setdefault('association', []).append(
                {
                    'ref_1': group_xid,
                    'ref_2': self.transformed_item['summary'],
                    'type_2': self.transformed_item['type'],
                }
            )
            self.log.info(
                'Added associated group with xid: %s to %s',
                group_xid,
                self.transformed_item['summary'],
            )

    def add_attribute(
        self,
        type_: str,
        value: str,
        displayed: bool = False,
        pinned: bool = False,
        source: str | None = None,
    ):
        """Add an attribute to the transformed item."""
        if type_ is not None and value is not None:
            attribute_data: dict[str, bool | str] = {
                'type': type_,
                'value': value,
            }

            # displayed is a special case, it only needs to be added if True
            if displayed is True:
                attribute_data['displayed'] = displayed

            # pinned is a special case, it only needs to be added if True
            if pinned is True:
                attribute_data['pinned'] = displayed

            # source is a special case, it only needs to be added if not None
            if source is not None:
                attribute_data['source'] = source

            self.transformed_item.setdefault('attribute', []).append(attribute_data)

    def add_file_occurrence(
        self,
        file_name: str | None = None,
        path: str | None = None,
        date: datetime | None = None,
    ):
        """Abstract method"""
        self.transformed_item.setdefault('fileOccurrence', []).append(
            {
                k: v
                for k, v in {
                    'fileName': file_name,
                    'path': path,
                    'date': date,
                }.items()
                if v
            }
        )

    def add_confidence(self, confidence: int | str | None):
        """Add a rating to the transformed item."""
        if confidence is not None:
            self.transformed_item['confidence'] = int(confidence)

    def add_group(self, group_data: dict):
        """Add a group to the transforms.

        Group data must match the format of the endpoint being used, (e.g., batch format
        for batch endpoints, v3 format for v3 endpoints).
        """
        self.adhoc_groups.append(group_data)

    def add_indicator(self, indicator_data: dict):
        """Add a indicator to the transforms.

        Indicator data must match the format of the endpoint being used, (e.g., batch format
        for batch endpoints, v3 format for v3 endpoints).
        """
        self.adhoc_indicators.append(indicator_data)

    def add_metadata(self, key: str, value: str):
        """Add name to the transformed item."""
        if all([key, value]):
            self.transformed_item[key] = value

    def add_name(self, name: str | None):
        """Add name to the transformed item."""
        if name is not None:
            self.transformed_item['name'] = name

    def add_rating(self, rating: float | str | None):
        """Add a rating to the transformed item."""
        if rating is not None:
            self.transformed_item['rating'] = float(rating)

    def add_security_label(
        self, name: str, color: str | None = None, description: str | None = None
    ):
        """Add a tag to the transformed item."""
        if name is not None:
            label_data = {'name': name}

            if color is not None:
                label_data['color'] = color

            if description is not None:
                label_data['description'] = description

            self.transformed_item.setdefault('securityLabel', []).append(label_data)

    def add_summary(self, value: str | None):
        """Add value1 to the transformed item."""
        if value is not None:
            self.transformed_item['summary'] = value

    def add_tag(self, name: str):
        """Add a tag to the transformed item."""
        if name is not None:
            self.transformed_item.setdefault('tag', []).append({'name': name})

    @property
    def batch(self) -> dict:
        """Return the data in batch format."""
        self._process()
        return dict(sorted(self.transformed_item.items()))

    @property
    def v3_api(self) -> dict:
        """Return the data in v3 format."""
        self._process()
        v3_data = {**self.transformed_item}

        # transform group associations
        if v3_data.get('associatedGroupXid'):
            v3_data['associatedGroups'] = {
                'data': [{'xid': g for g in v3_data['associatedGroupXid']}]  # noqa
            }
            del v3_data['associatedGroupXid']

        # transform attributes
        if v3_data.get('attribute'):
            v3_data['attributes'] = {
                'data': [
                    {
                        'type': a['type'],
                        'value': a['value'],
                        'pinned': a.get('pinned', False),
                        'source': a.get('source'),
                        # purposefully ignore the following fields, as they aren't part of the
                        # v3 API
                        # 'displayed': a.get('displayed', False),
                    }
                    for a in v3_data['attribute']
                ]
            }
            del v3_data['attribute']

        # transfomr tags
        if v3_data.get('tag'):
            v3_data['tags'] = {'data': [{'name': t['name']} for t in v3_data['tag']]}
            del v3_data['tag']

        # transform security labels
        if v3_data.get('securityLabel'):
            v3_data['securityLabels'] = {
                'data': [
                    {
                        'name': s['name'],
                        'color': s.get('color'),
                        'description': s.get('description'),
                    }
                    for s in v3_data['securityLabel']
                ]
            }
            del v3_data['securityLabel']

        # transform file occurrences
        if v3_data.get('fileOccurrence'):
            v3_data['fileOccurrences'] = {
                'data': [
                    {
                        'fileName': f.get('fileName'),
                        'path': f.get('path'),
                        'date': f.get('date'),
                    }
                    for f in v3_data['fileOccurrence']
                ]
            }
            del v3_data['fileOccurrence']

        return v3_data
