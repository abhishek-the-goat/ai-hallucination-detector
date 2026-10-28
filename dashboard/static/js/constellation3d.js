/**
 * constellation3d.js
 * ------------------
 * Interactive 3D Proposition Space for the Results page.
 * Uses Three.js & OrbitControls to render a central neural core with orbiting
 * 3D claim nodes. Features raycasting for mouse hover tooltips and click-to-focus.
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') return;

  const canvas = document.getElementById('constellation-canvas');
  const wrap = document.getElementById('constellation-wrap');
  const tooltip = document.getElementById('constellation-tooltip');
  if (!canvas || !wrap) return;

  const verdicts = window.VERDICTS_DATA || [];
  const score = window.HALLUCINATION_SCORE || 0;

  // Colors
  const COLOR_SUPPORTED = 0x10b981;
  const COLOR_CONTRADICTED = 0xef4444;
  const COLOR_UNVERIFIED = 0xf59e0b;
  const COLOR_CYAN = 0x00f0ff;

  let coreColor = COLOR_SUPPORTED;
  if (score >= 50) coreColor = COLOR_CONTRADICTED;
  else if (score >= 20) coreColor = COLOR_UNVERIFIED;

  // ── Renderer ───────────────────────────────────────────────────────
  const width = wrap.clientWidth || 400;
  const height = wrap.clientHeight || 280;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setSize(width, height, false);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100);
  camera.position.set(0, 3, 9);

  // ── OrbitControls ──────────────────────────────────────────────────
  let controls = null;
  if (typeof THREE.OrbitControls !== 'undefined') {
    controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.8;
    controls.enableZoom = true;
    controls.maxDistance = 16;
    controls.minDistance = 4;
  }

  // ── Central Neural Core ────────────────────────────────────────────
  const coreGroup = new THREE.Group();
  scene.add(coreGroup);

  const coreGeo = new THREE.IcosahedronGeometry(1.2, 2);
  const coreMat = new THREE.MeshBasicMaterial({
    color: coreColor,
    wireframe: true,
    transparent: true,
    opacity: 0.7,
  });
  const coreMesh = new THREE.Mesh(coreGeo, coreMat);
  coreGroup.add(coreMesh);

  // Inner nucleus
  const coreNuc = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 12, 12),
    new THREE.MeshBasicMaterial({ color: coreColor, transparent: true, opacity: 0.9 })
  );
  coreGroup.add(coreNuc);

  // Core orbit ring
  const coreRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.7, 0.02, 12, 60),
    new THREE.MeshBasicMaterial({ color: COLOR_CYAN, transparent: true, opacity: 0.4 })
  );
  coreRing.rotation.x = Math.PI / 2.5;
  coreGroup.add(coreRing);

  // ── Orbiting Claim Nodes ───────────────────────────────────────────
  const nodeMeshes = [];
  const linesGroup = new THREE.Group();
  scene.add(linesGroup);

  const total = Math.max(verdicts.length, 1);
  const orbitRadius = 4.2;

  verdicts.forEach((v, i) => {
    const angle = (i / total) * Math.PI * 2;
    const yOffset = (Math.sin(i * 1.5) * 1.2);
    const x = Math.cos(angle) * orbitRadius;
    const z = Math.sin(angle) * orbitRadius;
    const y = yOffset;

    let nodeColor = COLOR_UNVERIFIED;
    let nodeGeo = new THREE.OctahedronGeometry(0.38, 0);

    if (v.label === 'SUPPORTED') {
      nodeColor = COLOR_SUPPORTED;
      nodeGeo = new THREE.SphereGeometry(0.36, 12, 12);
    } else if (v.label === 'CONTRADICTED') {
      nodeColor = COLOR_CONTRADICTED;
      nodeGeo = new THREE.DodecahedronGeometry(0.42, 0);
    }

    const nodeMat = new THREE.MeshBasicMaterial({
      color: nodeColor,
      wireframe: false,
      transparent: true,
      opacity: 0.9,
    });

    const nodeMesh = new THREE.Mesh(nodeGeo, nodeMat);
    nodeMesh.position.set(x, y, z);
    nodeMesh.userData = {
      claim_id: v.claim_id,
      label: v.label,
      confidence: v.confidence,
      claim_text: v.claim_text,
      angle: angle,
      radius: orbitRadius,
      speed: 0.003 + (i % 3) * 0.001,
      baseY: y,
    };

    // Node halo ring
    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(0.55, 0.015, 8, 30),
      new THREE.MeshBasicMaterial({ color: nodeColor, transparent: true, opacity: 0.6 })
    );
    halo.rotation.x = Math.PI / 3;
    nodeMesh.add(halo);

    scene.add(nodeMesh);
    nodeMeshes.push(nodeMesh);

    // Connector line from core to node
    const lineMat = new THREE.LineBasicMaterial({
      color: nodeColor,
      transparent: true,
      opacity: 0.25,
    });
    const lineGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(x, y, z),
    ]);
    const line = new THREE.Line(lineGeo, lineMat);
    linesGroup.add(line);
    nodeMesh.userData.line = line;
  });

  // ── Raycasting for Mouse Interaction ──────────────────────────────
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2(-999, -999);
  let hoveredMesh = null;

  function onPointerMove(e) {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(nodeMeshes);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      if (hoveredMesh !== hit) {
        if (hoveredMesh) hoveredMesh.scale.set(1, 1, 1);
        hoveredMesh = hit;
        hit.scale.set(1.4, 1.4, 1.4);
      }
      canvas.style.cursor = 'pointer';

      // Tooltip position
      if (tooltip) {
        const d = hit.userData;
        const confPct = Math.round((d.confidence || 0) * 100);
        tooltip.innerHTML = `
          <div class="tt-header">
            <span class="tt-badge tt-${(d.label || '').toLowerCase()}">${d.label}</span>
            <span class="tt-conf">${confPct}%</span>
          </div>
          <div class="tt-title">Claim #${d.claim_id}</div>
          <div class="tt-text">${(d.claim_text || '').substring(0, 80)}…</div>
          <div class="tt-action">Click to view claim dossier ↓</div>
        `;
        tooltip.style.display = 'block';
        tooltip.style.left = `${e.clientX - rect.left + 14}px`;
        tooltip.style.top = `${e.clientY - rect.top + 14}px`;
      }
    } else {
      if (hoveredMesh) {
        hoveredMesh.scale.set(1, 1, 1);
        hoveredMesh = null;
      }
      canvas.style.cursor = 'default';
      if (tooltip) tooltip.style.display = 'none';
    }
  }

  function onClick(e) {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(nodeMeshes);

    if (intersects.length > 0) {
      const cid = intersects[0].object.userData.claim_id;
      const targetCard = document.getElementById(`claim-card-${cid}`);
      if (targetCard) {
        targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        targetCard.classList.add('pulse-glow');
        setTimeout(() => targetCard.classList.remove('pulse-glow'), 1500);
      }
    }
  }

  canvas.addEventListener('mousemove', onPointerMove);
  canvas.addEventListener('click', onClick);

  // Resize handler
  window.addEventListener('resize', () => {
    const newW = wrap.clientWidth;
    const newH = wrap.clientHeight;
    camera.aspect = newW / newH;
    camera.updateProjectionMatrix();
    renderer.setSize(newW, newH, false);
  }, { passive: true });

  // ── Animation Loop ─────────────────────────────────────────────────
  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const elapsed = clock.getElapsedTime();

    // Pulse core
    coreMesh.rotation.y += 0.005;
    coreMesh.rotation.z += 0.003;
    const pulse = 1.0 + Math.sin(elapsed * 2.5) * 0.08;
    coreMesh.scale.setScalar(pulse);

    coreRing.rotation.z += 0.008;

    // Orbit claim nodes
    nodeMeshes.forEach((mesh) => {
      const d = mesh.userData;
      d.angle += d.speed;
      mesh.position.x = Math.cos(d.angle) * d.radius;
      mesh.position.z = Math.sin(d.angle) * d.radius;
      mesh.position.y = d.baseY + Math.sin(elapsed * 1.5 + d.angle) * 0.3;
      mesh.rotation.y += 0.02;

      // Update connector line
      if (d.line) {
        const positions = d.line.geometry.attributes.position.array;
        positions[3] = mesh.position.x;
        positions[4] = mesh.position.y;
        positions[5] = mesh.position.z;
        d.line.geometry.attributes.position.needsUpdate = true;
      }
    });

    if (controls) controls.update();
    renderer.render(scene, camera);
  }

  animate();
})();
