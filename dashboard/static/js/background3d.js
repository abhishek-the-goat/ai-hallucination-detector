/**
 * background3d.js
 * ---------------
 * Lightweight Three.js animated 3D background: floating geometric shapes
 * and glowing particles reacting subtly to mouse movement.
 * Completely non-blocking (pointer-events: none, z-index: 0).
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') return;

  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x0a0e17, 1.0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 150);
  camera.position.z = 40;

  // ── Floating 3D Shapes ─────────────────────────────────────────────
  const SHAPE_COUNT = 18;
  const shapes = [];

  const geometries = [
    new THREE.IcosahedronGeometry(1.8, 0),
    new THREE.OctahedronGeometry(1.6, 0),
    new THREE.TetrahedronGeometry(2.0, 0),
  ];

  function rand(min, max) { return min + Math.random() * (max - min); }

  for (let i = 0; i < SHAPE_COUNT; i++) {
    const geo = geometries[i % geometries.length];
    const isCyan = i % 2 === 0;
    const mat = new THREE.MeshBasicMaterial({
      color: isCyan ? 0x00f0ff : 0x8b5cf6,
      wireframe: true,
      transparent: true,
      opacity: rand(0.12, 0.25),
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(rand(-40, 40), rand(-25, 25), rand(-20, 10));
    mesh.scale.setScalar(rand(0.7, 1.5));

    mesh.userData = {
      rotX: rand(-0.005, 0.005),
      rotY: rand(-0.005, 0.005),
      floatAmp: rand(0.6, 1.8),
      floatSpeed: rand(0.4, 0.9),
      baseY: mesh.position.y,
      phase: Math.random() * Math.PI * 2,
    };

    scene.add(mesh);
    shapes.push(mesh);
  }

  // ── Ambient Particles ──────────────────────────────────────────────
  const PARTICLE_COUNT = 250;
  const pPositions = new Float32Array(PARTICLE_COUNT * 3);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    pPositions[i * 3]     = rand(-50, 50);
    pPositions[i * 3 + 1] = rand(-30, 30);
    pPositions[i * 3 + 2] = rand(-30, 10);
  }

  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
  const pMat = new THREE.PointsMaterial({
    color: 0x38bdf8,
    size: 0.28,
    transparent: true,
    opacity: 0.5,
    sizeAttenuation: true,
  });
  const particles = new THREE.Points(pGeo, pMat);
  scene.add(particles);

  // ── Mouse Reactivity ───────────────────────────────────────────────
  let mouseX = 0, mouseY = 0;
  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }, { passive: true });

  // ── Animation Loop ─────────────────────────────────────────────────
  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    // Subtle camera tilt following mouse
    camera.position.x += (mouseX * 4 - camera.position.x) * 0.03;
    camera.position.y += (-mouseY * 3 - camera.position.y) * 0.03;
    camera.lookAt(0, 0, 0);

    // Animate shapes
    shapes.forEach((mesh) => {
      const d = mesh.userData;
      mesh.rotation.x += d.rotX;
      mesh.rotation.y += d.rotY;
      mesh.position.y = d.baseY + Math.sin(t * d.floatSpeed + d.phase) * d.floatAmp;
    });

    particles.rotation.y = t * 0.02;

    renderer.render(scene, camera);
  }

  animate();
})();
