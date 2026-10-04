"""Regression tests for scoped arithmetic, hostile identifiers and cloud projection."""
from copy import deepcopy
import unittest

from folio_api.demo_domain import DomainError, apply_action, compare_months, initial_state
from folio_api import finance_tools
from folio_api.providers.nebius import CloudProjection, EvidenceFact


class DomainCorrectnessTests(unittest.TestCase):
    def test_classify_rejects_unhashable_identifiers_without_mutation(self):
        state = initial_state()
        original = deepcopy(state)
        for ids in [[[]], [{}], [state['transactions'][0]['id'], []]]:
            with self.subTest(ids=ids), self.assertRaises(DomainError):
                apply_action(state, 'classify', {'ids': ids, 'purpose': 'business'})
        self.assertEqual(state, original)

    def test_split_rejects_unhashable_identifier_without_mutation(self):
        state = initial_state()
        original = deepcopy(state)
        for identifier in [[], {}, ['foreign']]:
            with self.subTest(identifier=identifier), self.assertRaises(DomainError):
                apply_action(state, 'split', {'id': identifier, 'businessPercent': 60})
        self.assertEqual(state, original)

    def test_transfers_are_excluded_from_categories_and_total_provenance(self):
        state = initial_state()
        transfer = {**state['transactions'][0], 'id': 'transfer-one', 'sourceId': 'source-transfer',
                    'date': '2026-09-15', 'category': 'Transfers', 'type': 'transfer', 'amountMinor': -999999}
        state['transactions'].append(transfer)
        result = compare_months(state, 'personal')
        self.assertEqual(result['currentMinor'], 341280)
        self.assertEqual(sum(row['currentMinor'] for row in result['rows']), result['currentMinor'])
        self.assertEqual(sum(row['differenceMinor'] for row in result['rows']), 39670)
        self.assertNotIn('Transfers', [row['category'] for row in result['rows']])
        self.assertNotIn('source-transfer', result['sourceIds'])

    def test_known_month_with_only_transfers_has_observed_zero_spending(self):
        state = initial_state()
        state['transactions'] = [{**state['transactions'][0], 'date': '2026-09-15', 'type': 'transfer'}]
        result = compare_months(state, 'personal')
        self.assertEqual(result['currentMinor'], 0)
        self.assertIsNone(result['previousMinor'])
        self.assertEqual(result['rows'], [])

    def test_goal_without_october_coverage_has_unknown_progress(self):
        goal = apply_action(initial_state(), 'save_goal', {'limitMinor': 30000})['goals'][0]
        self.assertIsNone(goal['spentMinor'])

    def test_goal_with_october_coverage_uses_actual_personal_eating_out(self):
        state = initial_state()
        state['transactions'].append({**state['transactions'][0], 'id': 'october-meal',
            'sourceId': 'source-october-meal', 'date': '2026-10-02', 'amountMinor': -1234,
            'purpose': 'split', 'businessPercent': 60})
        goal = apply_action(state, 'save_goal', {'limitMinor': 30000})['goals'][0]
        self.assertEqual(goal['spentMinor'], 494)


class GoalBaselineTests(unittest.IsolatedAsyncioTestCase):
    async def preview(self, state, scope='personal'):
        return await finance_tools.make_tool_executor(state, scope)('preview_goal', {'limitMinor': 30000}, 'op')

    async def test_baseline_is_exact_three_month_mean_with_explicit_rounding(self):
        state = initial_state()
        result = await self.preview(state)
        self.assertEqual(result['baselineMinor'], 58816)
        self.assertEqual(result['baselineTotalMinor'], 176450)
        self.assertEqual(result['baselinePeriods'], ['2026-07', '2026-08', '2026-09'])
        self.assertEqual(result['baselineRounding'], {'method': 'floor_to_minor_unit', 'divisor': 3, 'remainderNumerator': 2})
        self.assertTrue(result['baselineCoverageComplete'])
        self.assertIn('sourceIds', result)
        self.assertFalse(result['saved'])

    async def test_baseline_changes_with_scoped_corrections_and_never_mutates_source(self):
        state = initial_state()
        transaction = state['transactions'][0]
        changed = apply_action(state, 'classify', {'ids': [transaction['id']], 'purpose': 'business'})
        before = deepcopy(changed)
        personal = await self.preview(changed)
        business = await self.preview(changed, 'business')
        self.assertEqual(personal['baselineMinor'], (176450 + transaction['amountMinor']) // 3)
        self.assertEqual(business['baselineMinor'], -transaction['amountMinor'] // 3)
        self.assertNotEqual(personal['calculationId'], business['calculationId'])
        self.assertEqual(changed, before)
        self.assertEqual(changed['transactions'], state['transactions'])
        self.assertFalse(any('Only posted personal' in value for value in business['assumptions']))

    async def test_baseline_excludes_transfers_and_other_currencies(self):
        state = initial_state()
        row = state['transactions'][0]
        state['transactions'].extend([
            {**row, 'id': 'transfer', 'sourceId': 'transfer-source', 'type': 'transfer', 'amountMinor': -999999},
            {**row, 'id': 'usd-row', 'sourceId': 'usd-source', 'currency': 'USD', 'amountMinor': -999999},
        ])
        result = await self.preview(state)
        self.assertEqual(result['baselineMinor'], 58816)
        self.assertNotIn('transfer-source', result['sourceIds'])
        self.assertNotIn('usd-source', result['sourceIds'])

    async def test_missing_month_baseline_remains_unknown(self):
        state = initial_state()
        state['transactions'] = [row for row in state['transactions'] if not row['date'].startswith('2026-08')]
        result = await self.preview(state)
        self.assertIsNone(result['baselineMinor'])
        self.assertIsNone(result['baselineTotalMinor'])
        self.assertFalse(result['baselineCoverageComplete'])


class ProjectionTests(unittest.TestCase):
    def factory(self):
        factory = getattr(finance_tools, 'make_projection', None)
        self.assertTrue(callable(factory), 'A server-side typed projection factory is required')
        return factory

    def test_projection_is_typed_bounded_category_only_with_complete_provenance(self):
        state = initial_state()
        state['transactions'][0]['description'] = 'PRIVATE RAW DESCRIPTION MUST NOT LEAVE'
        projection = self.factory()(state, 'Why was September different?', 'personal')
        self.assertIsInstance(projection, CloudProjection)
        self.assertTrue(projection.synthetic)
        self.assertFalse(projection.owner_approved)
        self.assertTrue(1 <= len(projection.facts) <= 64)
        sources = {row['sourceId']: row for row in state['transactions']}
        september = 0
        for fact in projection.facts:
            self.assertIsInstance(fact, EvidenceFact)
            self.assertLessEqual(len(fact.source_ids), 64)
            self.assertTrue(set(fact.source_ids).issubset(sources))
            if fact.source_ids:
                rows = [sources[source] for source in fact.source_ids]
                self.assertEqual(len({row['category'] for row in rows}), 1)
                self.assertEqual(len({row['date'][:7] for row in rows}), 1)
                self.assertEqual(fact.amount_minor, -sum(row['amountMinor'] for row in rows))
                if rows[0]['date'].startswith('2026-09'):
                    september += fact.amount_minor
        self.assertEqual(september, 341280)
        self.assertNotIn('PRIVATE RAW DESCRIPTION', str(projection.as_dict()))

    def test_projection_refuses_non_demo_and_client_approval_flags(self):
        state = initial_state()
        state.update(kind='owner', synthetic=True, owner_approved=True)
        with self.assertRaises(DomainError):
            self.factory()(state, 'A question', 'personal')

    def test_projection_scope_and_question_are_bounded(self):
        for question, scope in [('', 'personal'), ('x' * 2001, 'personal'), ('Question', 'unknown'), ({'owner_approved': True}, 'personal')]:
            with self.subTest(scope=scope), self.assertRaises(DomainError):
                self.factory()(initial_state(), question, scope)

    def test_projection_refuses_to_truncate_category_source_records(self):
        state = initial_state()
        row = next(row for row in state['transactions'] if row['date'].startswith('2026-09') and row['category'] == 'Eating out')
        state['transactions'].extend({**row, 'id': f'extra-{i}', 'sourceId': f'source-extra-{i}'} for i in range(65))
        with self.assertRaises(DomainError):
            self.factory()(state, 'A question', 'personal')
