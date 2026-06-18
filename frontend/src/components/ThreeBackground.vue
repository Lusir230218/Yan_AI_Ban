<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'

const canvas = ref<HTMLCanvasElement>()

const props = withDefaults(defineProps<{
  particleCount?: number
  color?: string
  speed?: number
  connectDistance?: number
}>(), {
  particleCount: 120,
  color: '#a78bfa',
  speed: 0.3,
  connectDistance: 1.5,
})

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let particles: THREE.Points
let linesMesh: THREE.LineSegments
let animId: number

const particlePositions: THREE.Vector3[] = []
const geometry = new THREE.BufferGeometry()
const pointsMaterial = new THREE.PointsMaterial({
  size: 0.04,
  vertexColors: true,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  transparent: true,
  opacity: 0.8,
})
const lineGeometry = new THREE.BufferGeometry()
const lineMaterial = new THREE.LineBasicMaterial({
  vertexColors: true,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  transparent: true,
  opacity: 0.15,
})

function initScene() {
  const w = window.innerWidth; const h = window.innerHeight
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 50)
  camera.position.z = 5
  renderer = new THREE.WebGLRenderer({ canvas: canvas.value!, alpha: true, antialias: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x000000, 0)

  const baseColor = new THREE.Color(props.color)
  const count = props.particleCount
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const v = new THREE.Vector3(
      (Math.random() - 0.5) * 8, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 4,
    )
    particlePositions.push(v)
    positions[i * 3] = v.x; positions[i * 3 + 1] = v.y; positions[i * 3 + 2] = v.z
    const c = baseColor.clone()
    c.offsetHSL((Math.random() - 0.5) * 0.15, 0, (Math.random() - 0.5) * 0.3)
    colors[i * 3] = c.r; colors[i * 3 + 1] = c.g; colors[i * 3 + 2] = c.b
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  particles = new THREE.Points(geometry, pointsMaterial)
  scene.add(particles)
  updateLines()
  scene.add(linesMesh)
}

function updateLines() {
  const lineVerts: number[] = []; const lineColors: number[] = []
  const maxDist = props.connectDistance
  for (let i = 0; i < particlePositions.length; i++) {
    for (let j = i + 1; j < particlePositions.length; j++) {
      if (particlePositions[i].distanceTo(particlePositions[j]) < maxDist) {
        lineVerts.push(
          particlePositions[i].x, particlePositions[i].y, particlePositions[i].z,
          particlePositions[j].x, particlePositions[j].y, particlePositions[j].z,
        )
        for (let k = 0; k < 2; k++) lineColors.push(0.5, 0.5, 0.8)
      }
    }
  }
  lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(lineVerts, 3))
  lineGeometry.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 3))
  lineGeometry.setDrawRange(0, lineVerts.length / 3)
  if (linesMesh) { scene.remove(linesMesh); linesMesh.geometry.dispose() }
  linesMesh = new THREE.LineSegments(lineGeometry, lineMaterial)
}

function animate() {
  animId = requestAnimationFrame(animate)
  const rot = 0.005 * props.speed
  particles.rotation.y += rot
  linesMesh.rotation.y = particles.rotation.y
  renderer.render(scene, camera)
}

function onResize() {
  if (!renderer) return
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

onMounted(() => {
  initScene(); animate()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  geometry.dispose(); pointsMaterial.dispose()
  lineGeometry.dispose(); lineMaterial.dispose()
  renderer?.dispose()
})
</script>

<template>
  <canvas ref="canvas" class="three-bg" />
</template>

<style scoped>
.three-bg { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
</style>
