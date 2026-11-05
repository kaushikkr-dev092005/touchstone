from pathlib import Path
import ast
import os
import subprocess
import sys
import unittest


class FundingProbeTests(unittest.TestCase):
    def test_funding_preconditions_survive_python_optimization(self):
        path = Path(__file__).resolve().parent.parent/'tools/fund_metal_probe.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)))
        guard = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'require')
        namespace = {}
        exec(compile(ast.Module(body=[guard], type_ignores=[]), str(path), 'exec', optimize=2), namespace)
        with self.assertRaises(ValueError):
            namespace['require'](False)

    def test_no_execute_stops_before_loading_private_configuration(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run([sys.executable, str(root/'tools/fund_metal_probe.py')],
            env={**os.environ, 'TOUCHSTONE_IGNORE_LOCAL_CONFIG': '1'},
            cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--execute', result.stderr)
        self.assertNotIn('METAL_RPC_URL', result.stdout)


if __name__ == '__main__':
    unittest.main()
