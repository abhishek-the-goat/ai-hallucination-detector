/**
 * heroOrb.js
 * ----------
 * Renders an interactive 3D Holographic AI Neural Orb on the landing page.
 * Uses Three.js with wireframe geometry, glowing points, and gyro rings.
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') return;

  const canvas = document.getElementById('hero-orb-canvas');
  if (!canvas) return;

  const width = canvas.clientWidth || 320;
  const height = canvas.clientHeight || 260;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setSize(width, height, false);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
  camera.position.z = 7;

  // ── Central Pulsing Icosahedron Core ────────────────────────────────
  const coreGeo = new THREE.IcosahedronGeometry(1.6, 2);
  const coreMat = new THREE.MeshBasicMaterial({
    color: 0x00f0ff,
    wireframe: true,
    transparent: true,
    opacity: 0.45,
  });
  const coreMesh = new THREE.Mesh(coreGeo, coreMat);
  scene.add(coreMesh);

  // ── Inner Nucleus Sphere ───────────────────────────────────────────
  const nucGeo = new THREE.SphereGeometry(0.8, 16, 16);
  const nucMat = new THREE.MeshBasicMaterial({
    color: 0x8b5cf6,
    wireframe: true,
    transparent: true,
    opacity: 0.6,
  });
  const nucMesh = new THREE.Mesh(nucGeo, nucMat);
  scene.add(nucMesh);

  // ── Outer Holographic Gyro Rings ───────────────────────────────────
  const ring1Geo = new THREE.TorusGeometry(2.3, 0.025, 16, 80);
  const ring1Mat = new THREE.MeshBasicMaterial({ color: 0x00f0ff, transparent: true, opacity: 0.5 });
  const ring1 = new THREE.Mesh(ring1Geo, ring1Mat);
  ring1.rotation.x = Math.PI / 3;
  scene.add(ring1);

  const ring2Geo = new THREE.TorusGeometry(2.6, 0.02, 16, 80);
  const ring2Mat = new THREE.MeshBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.4 });
  const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
  ring2.rotation.y = Math.PI / 4;
  scene.add(ring2);

  // ── Particle Swarm ─────────────────────────────────────────────────
  const pCount = 70;
  const pPos = new Float32Array(pCount * 3);
  for (let i = 0; i < pCount; i++) {
    const u = Math.random();
    const v = Math.random();
    const theta = u * 2.0 * Math.PI;
    const phi = Math.acos(2.0 * v - 1.0);
    const r = 2.0 + Math.random() * 0.9;
    pPos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
    pPos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pPos[i * 3 + 2] = r * Math.cos(phi);
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
  const pMat = new THREE.PointsMaterial({
    color: 0x00f0ff,
    size: 0.06,
    transparent: true,
    opacity: 0.8,
  });
  const particles = new THREE.Points(pGeo, pMat);
  scene.add(particles);

  // ── Mouse interaction ──────────────────────────────────────────────
  let targetRotX = 0;
  let targetRotY = 0;

  window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    targetRotY = (e.clientX - cx) * 0.002;
    targetRotX = (e.clientY - cy) * 0.002;
  }, { passive: true });

  // ── Animation Loop ─────────────────────────────────────────────────
  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const elapsed = clock.getElapsedTime();

    coreMesh.rotation.y += 0.006;
    coreMesh.rotation.x += 0.004;

    nucMesh.rotation.y -= 0.008;
    nucMesh.rotation.z += 0.005;

    // Pulse core scale
    const pulse = 1.0 + Math.sin(elapsed * 2.5) * 0.06;
    coreMesh.scale.setScalar(pulse);

    ring1.rotation.z += 0.008;
    ring2.rotation.x += 0.007;
    particles.rotation.y -= 0.003;

    // Smooth mouse tilt
    scene.rotation.y += (targetRotY - scene.rotation.y) * 0.05;
    scene.rotation.x += (targetRotX - scene.rotation.x) * 0.05;

    renderer.render(scene, camera);
  }

  animate();
})();
