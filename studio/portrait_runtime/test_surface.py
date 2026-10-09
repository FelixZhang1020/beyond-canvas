"""Run with the isolated mesh runtime: python -m unittest studio.portrait_runtime.test_surface."""
import unittest
from unittest.mock import patch

import numpy as np
import trimesh

from studio.making import mesh
from studio.portrait_runtime.server import prepare_surface


class SurfaceTests(unittest.TestCase):
    def surface(self):
        surface = trimesh.creation.icosphere(subdivisions=4)
        # Fine field-sampling ripples on a rounded surface, independent of a
        # model or any private drawing. Both subject modes see the same input.
        surface.vertices *= (1 + .004*np.sin(surface.vertices[:,1]*65))[:,None]
        return surface

    def test_fruit_smoothing_reduces_ripples_within_the_same_mesh_budget(self):
        head = prepare_surface(self.surface())
        fruit = prepare_surface(self.surface(), subject="fruit")
        def roughness(data):
            p = np.array(data["positions"]).reshape(-1,3)
            p -= (p.min(axis=0)+p.max(axis=0))/2
            radial = p/np.linalg.norm(p,axis=1)[:,None]
            normals = np.array(data["normals"]).reshape(-1,3)
            # Remove the sphere's real curvature from the measurement: only
            # deviation from its radial normals counts as a sampling ripple.
            return np.mean(np.linalg.norm(normals-radial,axis=1)**2)
        self.assertLess(roughness(fruit), roughness(head)*.7)
        self.assertEqual(len(fruit["indices"]), len(head["indices"]))
        self.assertEqual(mesh.validate(fruit), fruit)
        for size in fruit["size"]:
            self.assertTrue(2.9 < size < 3.1)

    def test_fragmented_surfaces_remain_refused_for_both_subjects(self):
        a,b = self.surface(),self.surface()
        b.apply_translation([4,0,0])
        bad = trimesh.util.concatenate([a,b])
        for subject in ("head", "fruit"):
            prepare_surface(a.copy(), subject=subject)
            with self.assertRaisesRegex(ValueError, "fragmented"):
                prepare_surface(bad.copy(), subject=subject)

    def test_excessive_smoothing_displacement_is_rejected(self):
        prepare_surface(self.surface(), subject="fruit")
        def excessive(surface, **_):
            surface.vertices[:,0] += .1
        with patch("trimesh.smoothing.filter_taubin", excessive):
            with self.assertRaisesRegex(ValueError, "unstable"):
                prepare_surface(self.surface(), subject="fruit")


if __name__ == "__main__":
    unittest.main()
