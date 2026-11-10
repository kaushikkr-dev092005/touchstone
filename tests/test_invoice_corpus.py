import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from touchstone.invoice_corpus import freeze,load
from touchstone.invoice_dataset import build
from touchstone.invoice_extraction import source_spans,verify
from touchstone.invoice_profile import corpus_records,raw_profile
from touchstone.invoice_study import evaluate_profile,report
from touchstone.workload import Task


class FrozenCorpusTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)/'corpus'
        self.manifest=freeze(self.root,202611101)

    def test_prospective_holdout_is_new_disjoint_and_write_once(self):
        manifest,records,_=load(self.root)
        self.assertEqual(manifest['partition_counts'],{'calibration':120,'holdout':60})
        old=build()[0];old_hashes={r['source_sha256'] for r in old}
        new_holdout=[r for r in records if r['partition']=='holdout']
        self.assertFalse(old_hashes & {r['source_sha256'] for r in new_holdout})
        self.assertFalse({r['template_id'] for r in records if r['partition']=='calibration'} &
            {r['template_id'] for r in new_holdout})
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(freeze(self.root,202611101),manifest)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})
        with self.assertRaises(ValueError):freeze(self.root,202611102)
        self.assertEqual(manifest['model_calls_at_freeze'],0)

    def test_model_can_select_every_truth_span_without_receiving_truth(self):
        _,records,truth=load(self.root,include_truth=True)
        for record in records:
            task=Task(**record['task']);spans,_=source_spans(task)
            positions={(s['start'],s['end']) for s in spans.values()}
            output=truth[task.id]['output']
            for span in [s for s in output['fields'].values() if s]+[s for item in output['items'] for s in item.values()]:
                self.assertIn((span['start'],span['end']),positions,task.id)
            self.assertEqual(set(task.source),{'text','purchase_order','payments'})

    def test_profiler_loads_sources_without_opening_offline_truth(self):
        original=Path.read_bytes
        def guarded(path):
            if path.name=='offline-truth.json':raise AssertionError('Profiler accessed truth')
            return original(path)
        with patch.object(Path,'read_bytes',guarded):
            records,binding=corpus_records(self.root)
        self.assertEqual(len(records),180)
        self.assertEqual(binding['corpus_sources_sha256'],self.manifest['sources_sha256'])

    def test_changed_sources_or_truth_are_refused(self):
        source=self.root/'sources.jsonl';original=source.read_bytes()
        source.write_bytes(original+b'\n')
        with self.assertRaises(ValueError):load(self.root)
        source.write_bytes(original)
        truth=self.root/'offline-truth.json';truth.write_bytes(truth.read_bytes()+b'\n')
        load(self.root,include_truth=False)
        with self.assertRaises(ValueError):load(self.root,include_truth=True)

    def test_unfamiliar_roles_require_review_even_for_exact_extractions(self):
        _,records,truth=load(self.root,include_truth=True)
        for record in records:
            if record['partition']!='holdout':continue
            task=Task(**record['task']);verdict=verify(task,truth[task.id]['output'])
            self.assertEqual(verdict['decision'],'review',task.id)
            self.assertFalse(verdict['passed']);self.assertFalse(verdict['payment_authorized'])

    def test_profile_binding_and_unchanged_thresholds_are_enforced(self):
        manifest,records,truth=load(self.root,include_truth=True)
        raw=raw_profile('fixture','fixture',[],dataset_version=manifest['dataset_version'],corpus_sources_sha256='wrong')
        with self.assertRaises(ValueError):
            evaluate_profile(records,truth,raw,dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
        result=report(Path(self.directory.name)/'report',corpus=self.root)
        self.assertFalse(result['threshold_changed'])
        self.assertEqual(result['models_measured'],0)
        self.assertEqual(result['qualification_status'],'BLOCKED_NO_ELIGIBLE_MODEL')


if __name__=='__main__':unittest.main()
