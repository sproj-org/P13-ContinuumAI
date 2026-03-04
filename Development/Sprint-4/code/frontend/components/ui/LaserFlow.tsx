"use client";

import { useRef, useMemo, Suspense, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

interface LaserFlowProps {
  className?: string;
  style?: React.CSSProperties;
  color1?: string;
  color2?: string;
  particleCount?: number;
  speed?: number;
}

interface LaserParticlesProps {
  count: number;
  color1: string;
  color2: string;
  speed: number;
}

const LaserParticles = ({ count, color1, color2, speed }: LaserParticlesProps) => {
  const meshRef = useRef<THREE.Points>(null);
  
  const [geometry, velocities] = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const vel = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    const c1 = new THREE.Color(color1);
    const c2 = new THREE.Color(color2);
    
    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      
      // Position - spread across a wide area
      positions[i3] = (Math.random() - 0.5) * 20;
      positions[i3 + 1] = (Math.random() - 0.5) * 10;
      positions[i3 + 2] = (Math.random() - 0.5) * 10;
      
      // Velocity - mostly horizontal movement
      vel[i3] = (Math.random() * 0.5 + 0.5) * speed;
      vel[i3 + 1] = (Math.random() - 0.5) * 0.1;
      vel[i3 + 2] = (Math.random() - 0.5) * 0.1;
      
      // Color - interpolate between two colors
      const t = Math.random();
      colors[i3] = c1.r + (c2.r - c1.r) * t;
      colors[i3 + 1] = c1.g + (c2.g - c1.g) * t;
      colors[i3 + 2] = c1.b + (c2.b - c1.b) * t;
    }
    
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    
    return [geo, vel];
  }, [count, color1, color2, speed]);

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    
    const positionAttr = meshRef.current.geometry.attributes.position;
    const positionArray = positionAttr.array as Float32Array;
    
    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      
      positionArray[i3] += velocities[i3] * delta;
      positionArray[i3 + 1] += velocities[i3 + 1] * delta;
      positionArray[i3 + 2] += velocities[i3 + 2] * delta;
      
      // Reset particles that go too far
      if (positionArray[i3] > 10) {
        positionArray[i3] = -10;
      }
    }
    
    positionAttr.needsUpdate = true;
  });

  return (
    <points ref={meshRef} geometry={geometry}>
      <pointsMaterial
        size={0.05}
        vertexColors
        transparent
        opacity={0.8}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};

const LaserLines = ({ color1, color2, speed }: { color1: string; color2: string; speed: number }) => {
  const groupRef = useRef<THREE.Group>(null);
  const { scene } = useThree();
  
  const lines = useMemo(() => {
    const lineData = [];
    const lineCount = 15;
    
    for (let i = 0; i < lineCount; i++) {
      const y = (i / lineCount - 0.5) * 8;
      const z = (Math.random() - 0.5) * 5;
      const startX = -10 + Math.random() * 2;
      const length = 2 + Math.random() * 4;
      const t = i / lineCount;
      
      lineData.push({
        start: new THREE.Vector3(startX, y, z),
        end: new THREE.Vector3(startX + length, y, z),
        color: new THREE.Color(color1).lerp(new THREE.Color(color2), t),
        speed: 0.5 + Math.random() * speed,
        offset: Math.random() * 20,
      });
    }
    
    return lineData;
  }, [color1, color2, speed]);

  useEffect(() => {
    if (!groupRef.current) return;
    
    // Create lines imperatively
    lines.forEach((line) => {
      const geometry = new THREE.BufferGeometry().setFromPoints([line.start, line.end]);
      const material = new THREE.LineBasicMaterial({
        color: line.color,
        transparent: true,
        opacity: 0.4,
      });
      const mesh = new THREE.Line(geometry, material);
      groupRef.current?.add(mesh);
    });

    return () => {
      groupRef.current?.children.forEach((child) => {
        if (child instanceof THREE.Line) {
          child.geometry.dispose();
          (child.material as THREE.LineBasicMaterial).dispose();
        }
      });
    };
  }, [lines]);

  useFrame((state) => {
    if (!groupRef.current) return;
    
    groupRef.current.children.forEach((child, index) => {
      const line = lines[index];
      if (line) {
        const offset = (state.clock.elapsedTime * line.speed + line.offset) % 20 - 10;
        child.position.x = offset;
      }
    });
  });

  return <group ref={groupRef} />;
};

const Scene = ({ color1, color2, particleCount, speed }: Omit<LaserFlowProps, 'className' | 'style'> & { particleCount: number }) => {
  return (
    <>
      <LaserParticles count={particleCount} color1={color1!} color2={color2!} speed={speed!} />
      <LaserLines color1={color1!} color2={color2!} speed={speed!} />
    </>
  );
};

export const LaserFlow = ({
  className = '',
  style,
  color1 = '#3b82f6',
  color2 = '#8b5cf6',
  particleCount = 500,
  speed = 2,
}: LaserFlowProps) => {
  return (
    <div
      className={`absolute inset-0 pointer-events-none ${className}`}
      style={style}
    >
      <Canvas
        camera={{ position: [0, 0, 8], fov: 60 }}
        gl={{ 
          antialias: true, 
          alpha: true,
          powerPreference: 'high-performance',
        }}
      >
        <Suspense fallback={null}>
          <Scene 
            color1={color1} 
            color2={color2} 
            particleCount={particleCount} 
            speed={speed} 
          />
        </Suspense>
      </Canvas>
    </div>
  );
};

export default LaserFlow;
