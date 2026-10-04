import unittest
from folio_api.demo_domain import initial_state, apply_action, compare_months, split_amount, DomainError

class DemoDomainTests(unittest.TestCase):
    def test_fixture_has_341_immutable_rows(self):
        state = initial_state()
        self.assertEqual(len(state['transactions']), 341)
        self.assertEqual(len({t['id'] for t in state['transactions']}), 341)
        self.assertTrue(all(type(t['amountMinor']) is int for t in state['transactions']))
    def test_paper_comparison_reconciles(self):
        result = compare_months(initial_state(), 'personal')
        self.assertEqual(result['previousMinor'], 301610)
        self.assertEqual(result['currentMinor'], 341280)
        self.assertEqual(result['differenceMinor'], 39670)
        self.assertEqual(sum(r['differenceMinor'] for r in result['rows']),39670)
    def test_split_exact_conservation(self):
        self.assertEqual(split_amount(-8900,60),(-5340,-3560))
        self.assertEqual(sum(split_amount(-8999,33)),-8999)
    def test_split_rejects_range(self):
        for pct in [-1,101,2.5,True]:
            with self.assertRaises(DomainError): split_amount(-8900,pct)
    def test_saved_goal_is_durable_domain_state(self):
        state = initial_state(); after=apply_action(state,'save_goal',{'limitMinor':50000})
        self.assertEqual(after['goals'][0]['limitMinor'],50000)
        self.assertEqual(state['goals'],[])
    def test_action_undo_restores_annotations(self):
        state=initial_state(); tid=state['transactions'][0]['id']
        changed=apply_action(state,'classify',{'ids':[tid],'purpose':'business','remember':True})
        self.assertEqual(changed['annotations'][tid]['purpose'],'business')
        restored=apply_action(changed,'undo',{})
        self.assertEqual(restored['annotations'],state['annotations'])
        self.assertEqual(restored['memory'],state['memory'])
        self.assertEqual(restored['transactions'],state['transactions'])
    def test_unknown_id_rejected(self):
        with self.assertRaises(DomainError): apply_action(initial_state(),'classify',{'ids':['missing'],'purpose':'business'})
    def test_goal_bounds(self):
        for amount in [0,-1,500.2,True,10**10]:
            with self.assertRaises(DomainError): apply_action(initial_state(),'save_goal',{'limitMinor':amount})
    def test_amount_cannot_be_modified(self):
        before=initial_state(); tid=before['transactions'][0]['id']
        after=apply_action(before,'split',{'id':tid,'businessPercent':60})
        self.assertEqual(before['transactions'],after['transactions'])
    def test_no_money_movement_action(self):
        for action in ['pay','transfer','buy','cancel_subscription','apply_grant']:
            with self.assertRaises(DomainError): apply_action(initial_state(),action,{})
    def test_scope_is_explicit(self):
        with self.assertRaises(DomainError): compare_months(initial_state(),'unknown')
    def test_no_empty_zero_claim(self):
        state=initial_state(); state['transactions']=[]
        result=compare_months(state,'personal')
        self.assertIsNone(result['currentMinor'])
        self.assertIsNone(result['differenceMinor'])

if __name__=='__main__': unittest.main()
