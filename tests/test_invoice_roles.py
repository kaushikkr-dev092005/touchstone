import copy
import unittest
from unittest.mock import patch

from touchstone.invoice_dataset import build
from touchstone.invoice_extraction import verify
from touchstone.invoice_study import metrics,score
from touchstone.workload import Task


def fixture():
    values={'invoice_id':'INV-2026','supplier_name':'Acme Supply','purchase_order_id':'PO-2026',
        'currency':'USD','subtotal_cents':'USD 2.00','tax_cents':'USD 2.00','total_cents':'USD 4.00'}
    labels=['Invoice ID','Supplier','Purchase order','Currency','Subtotal','Tax','Total due']
    lines=[];fields={};offset=0
    for (role,value),label in zip(values.items(),labels):
        line=label+': '+value
        begin=offset+len(label)+2
        fields[role]={'value':value,'start':begin,'end':begin+len(value)}
        lines.append(line);offset+=len(line)+1
    row='ITEM-01 | quantity=1 | unit=USD 2.00 | amount=USD 2.00'
    item={'line':{'value':row,'start':offset,'end':offset+len(row)}}
    for role,label,value in [('quantity','quantity=','1'),('unit_price_cents','unit=','USD 2.00'),
        ('line_total_cents','amount=','USD 2.00')]:
        begin=offset+row.index(label)+len(label)
        item[role]={'value':value,'start':begin,'end':begin+len(value)}
    lines.append(row)
    task=Task('task-id-is-not-an-invoice-id','invoice_extraction',{'text':'\n'.join(lines),
        'purchase_order':{'purchase_order_id':'PO-2026','supplier_name':'Acme Supply','currency':'USD','authorized_cents':1000},
        'payments':[]})
    return task,{'fields':fields,'items':[item]}


class InvoiceRoleTests(unittest.TestCase):
    def setUp(self):self.task,self.output=fixture()

    def test_valid_roles_use_source_not_task_identity_or_offline_truth(self):
        with patch('touchstone.invoice_dataset.build',side_effect=AssertionError('Offline truth accessed')):
            verdict=verify(self.task,self.output)
        self.assertTrue(verdict['passed']);self.assertEqual(verdict['decision'],'candidate')
        self.assertTrue(verdict['semantic_role_binding_verified'])
        self.assertFalse(verdict['payment_authorized'])

    def test_label_selection_is_rejected_even_with_correct_arithmetic(self):
        for role,label in [('invoice_id','Invoice ID'),('supplier_name','Supplier'),('purchase_order_id','Purchase order')]:
            output=copy.deepcopy(self.output);begin=self.task.source['text'].index(label)
            output['fields'][role]={'value':label,'start':begin,'end':begin+len(label)}
            verdict=verify(self.task,output)
            self.assertTrue(verdict['arithmetic_valid'])
            self.assertEqual(verdict['decision'],'rejected')
            self.assertFalse(verdict['passed'])
            self.assertIn('FIELD_ROLE_MISMATCH:'+role,verdict['issues'])

    def test_equal_value_header_swaps_and_item_swaps_still_reject(self):
        for header in (True,False):
            output=copy.deepcopy(self.output)
            mapping=output['fields'] if header else output['items'][0]
            a,b=('subtotal_cents','tax_cents') if header else ('unit_price_cents','line_total_cents')
            mapping[a],mapping[b]=mapping[b],mapping[a]
            verdict=verify(self.task,output)
            self.assertTrue(verdict['arithmetic_valid'])
            self.assertEqual(verdict['decision'],'rejected');self.assertFalse(verdict['passed'])

    def test_identical_or_conflicting_duplicate_headers_are_reviewed(self):
        for suffix in ('Invoice ID: INV-2026','Invoice ID: INV-OTHER'):
            task=copy.deepcopy(self.task);task.source['text']+='\n'+suffix
            verdict=verify(task,self.output)
            self.assertEqual(verdict['decision'],'review');self.assertFalse(verdict['passed'])
            self.assertIn('AMBIGUOUS_HEADER_ROLE:invoice_id',verdict['issues'])

    def test_role_swaps_never_pass_across_all_existing_layouts(self):
        records,truth=build();checked=0
        for record in records:
            task=Task(**record['task']);output=copy.deepcopy(truth[task.id]['output'])
            if any(value is None for value in output['fields'].values()):continue
            output['fields']['invoice_id'],output['fields']['purchase_order_id']=output['fields']['purchase_order_id'],output['fields']['invoice_id']
            verdict=verify(task,output)
            self.assertTrue(verdict['arithmetic_valid'])
            self.assertEqual(verdict['decision'],'rejected',task.id)
            self.assertFalse(verdict['passed']);checked+=1
        self.assertEqual(checked,144)

    def test_ocr_role_corruption_abstains_but_unrelated_noise_is_harmless(self):
        task=copy.deepcopy(self.task);task.source['text']=task.source['text'].replace('Supplier:','Suppl1er:')
        verdict=verify(task,self.output)
        self.assertEqual(verdict['decision'],'review');self.assertFalse(verdict['passed'])
        self.assertIn('UNSUPPORTED_HEADER_ROLE:supplier_name',verdict['issues'])
        task=copy.deepcopy(self.task);task.source['text']+='\nScanned c0py / receiv1ng n0tes [OCR]'
        self.assertTrue(verify(task,self.output)['passed'])

    def test_po_mismatch_and_duplicate_payment_ids_are_never_candidates(self):
        for duplicate in (False,True):
            task=copy.deepcopy(self.task)
            if duplicate:
                payment={'payment_id':'PAY-1','invoice_id':'INV-2026','purchase_order_id':'PO-2026',
                    'supplier_name':'Acme Supply','currency':'USD','amount_cents':400,'status':'failed'}
                task.source['payments']=[payment,dict(payment)]
            else:task.source['purchase_order']['purchase_order_id']='PO-OTHER'
            verdict=verify(task,self.output)
            self.assertEqual(verdict['decision'],'review');self.assertFalse(verdict['passed'])
            self.assertTrue(verdict['semantic_role_binding_verified']);self.assertTrue(verdict['arithmetic_valid'])

    def test_duplicate_line_identifier_is_reviewed(self):
        records,truth=build();record=records[0];task=Task(**copy.deepcopy(record['task']))
        output=copy.deepcopy(truth[task.id]['output'])
        task.source['text']=task.source['text'].replace('ITEM-02','ITEM-01')
        output['items'][1]['line']['value']=output['items'][1]['line']['value'].replace('ITEM-02','ITEM-01')
        verdict=verify(task,output)
        self.assertEqual(verdict['decision'],'review');self.assertFalse(verdict['passed'])
        self.assertIn('DUPLICATE_LINE_IDENTIFIER',verdict['issues'])

    def test_correct_review_is_not_counted_as_an_acceptance(self):
        records,truth=build();record=next(r for r in records if r['scenario']=='conflicting_po')
        identity=record['task']['id']
        rows=score(records,truth,[{'task_id':identity,'output':truth[identity]['output'],'latency_ms':1}])
        rows[0]['verifier_passed']=True # Older persisted rows cannot promote a review either.
        result=metrics(rows)
        self.assertEqual(result['strict_correct'],1)
        self.assertEqual((result['candidates'],result['review'],result['rejected']),(0,1,0))
        self.assertEqual(result['accepted'],0);self.assertEqual(result['false_accepts'],0)


if __name__=='__main__':unittest.main()
