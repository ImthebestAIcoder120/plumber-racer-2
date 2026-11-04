"""dmsh_build.py spill_shared and reflect on synthetic MSL: a kernel whose shared arrays pass Metal's 32 KB (Mario Kart World's declare 48 KB) reads them from a slice of a device buffer
per threadgroup, indexed by the threadgroup's place in the grid, and its barriers order device memory too; the buffer is a new argument buffer member after every other, reflected with its
bytes per threadgroup; a kernel within the limit, and the other stages, stay as they are."""
import ast
from pathlib import Path
import re
import sys
import types
import unittest

TOOLS = Path(__file__).resolve().parents[2] / 'gfx/tools'
sys.path.insert(0, str(TOOLS))
import dmsh_abi as abi   # noqa: E402

FUNCS = {'decode_tex', 'const_sampler', 'decode_ubo_tex', 'c2_array', 'spill_shared', 'reflect'}
NAMES = {'SPILL_DECL', 'SPILL_SIZE', 'TEX_BASE', 'SSBO'}


def load():
    tree = ast.parse((TOOLS / 'dmsh_build.py').read_text())
    nodes: list[ast.stmt] = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in FUNCS)
             or (isinstance(n, ast.Assign) and any(isinstance(t, (ast.Name, ast.Tuple)) and {getattr(e, 'id', None) for e in (t.elts if isinstance(t, ast.Tuple) else [t])} & NAMES for t in n.targets))]
    ns = {'re': re, 'abi': abi, 'dmsh_geometry': types.SimpleNamespace(HELPERS={})}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(TOOLS / 'dmsh_build.py'), 'exec'), ns)
    assert FUNCS <= set(ns), FUNCS - set(ns)
    return ns


NS = load()


def kernel(n, params='uint3 gl_WorkGroupID [[threadgroup_position_in_grid]], uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]]'):
    return f'''struct spvDescriptorSetBuffer0
{{
    constant _10* support_buffer [[id(0)]];
    array<texture2d<float>, 32> cp_t2d_cb14_0 [[id(1)]];
    device _29* cp_s0 [[id(33)]];
}};

kernel void main0(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], {params})
{{
    threadgroup spvUnsafeArray<uint, {n}> _37;
    _37[int(gl_LocalInvocationID.x)] = 1u;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint v = _37[0];
}}
'''


class Spill(unittest.TestCase):
    def test_rewrite(self):
        out = NS['spill_shared'](kernel(12288))
        self.assertNotIn('threadgroup spvUnsafeArray', out)
        self.assertIn(f'    device uint* {abi.SPILL_MEMBER} [[id(34)]];   // 49152 bytes per threadgroup\n}};', out)
        self.assertIn('uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]], uint3 dm_spill_n [[threadgroups_per_grid]])', out)
        self.assertIn('+ ulong((gl_WorkGroupID.z * dm_spill_n.y + gl_WorkGroupID.y) * dm_spill_n.x + gl_WorkGroupID.x) * 49152u;', out)
        self.assertIn('    device uint* _37 = (device uint*)(dm_spill_base + 0);\n', out)
        self.assertIn('threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);', out)
        b = NS['reflect']('k', 'cs', out, {'sbufs': [{'binding': 0, 'cb_slot': 0, 'cb_offset': 0, 'flags': 1}]})
        self.assertEqual([(e['msl_name'], e['arg_id']) for e in b][-1], (abi.SPILL_MEMBER, 34))
        self.assertEqual((b[-1]['kind'], b[-1]['bytes'], b[-1]['rw']), (abi.KIND_SPILL, 49152, True))

    def test_threadgroup_id_added(self):
        out = NS['spill_shared'](kernel(12288, 'uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]]'))
        self.assertIn('uint3 dm_spill_id [[threadgroup_position_in_grid]], uint3 dm_spill_n [[threadgroups_per_grid]])', out)
        self.assertIn('ulong((dm_spill_id.z * dm_spill_n.y + dm_spill_id.y) * dm_spill_n.x + dm_spill_id.x)', out)

    def test_within_the_limit_stays(self):
        src = kernel(8192)   # 32 KB exactly
        self.assertEqual(NS['spill_shared'](src), src)

    def test_other_shared_memory_refused(self):
        src = kernel(12288).replace('    _37[int(', '    threadgroup float4 _40[4];\n    _37[int(', 1)
        with self.assertRaises(ValueError): NS['spill_shared'](src)


if __name__ == '__main__':
    unittest.main()
