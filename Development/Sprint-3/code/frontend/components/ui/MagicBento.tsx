"use client";

import { useRef, useEffect, ReactNode, Children, cloneElement, isValidElement } from 'react';
import { gsap } from 'gsap';

interface MagicBentoProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  glow?: boolean;
  glowColor?: string;
  tiltStrength?: number;
}

interface MagicBentoItemProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  colSpan?: 1 | 2 | 3;
  rowSpan?: 1 | 2;
}

export const MagicBento = ({
  children,
  className = '',
  style,
  glow = true,
  glowColor = 'rgba(59, 130, 246, 0.5)',
  tiltStrength = 10,
}: MagicBentoProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const cards = container.querySelectorAll('.magic-bento-item');
    const cleanupFunctions: Array<() => void> = [];

    cards.forEach((card) => {
      const cardElement = card as HTMLElement;
      const glowElement = cardElement.querySelector('.bento-glow') as HTMLElement;

      const handleMouseMove = (e: MouseEvent) => {
        const rect = cardElement.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const mouseX = e.clientX - centerX;
        const mouseY = e.clientY - centerY;

        const rotateX = (mouseY / (rect.height / 2)) * -tiltStrength;
        const rotateY = (mouseX / (rect.width / 2)) * tiltStrength;

        gsap.to(cardElement, {
          rotateX,
          rotateY,
          duration: 0.5,
          ease: 'power2.out',
          transformPerspective: 1000,
        });

        if (glowElement && glow) {
          const glowX = ((e.clientX - rect.left) / rect.width) * 100;
          const glowY = ((e.clientY - rect.top) / rect.height) * 100;
          gsap.to(glowElement, {
            background: `radial-gradient(circle at ${glowX}% ${glowY}%, ${glowColor}, transparent 50%)`,
            opacity: 1,
            duration: 0.3,
          });
        }
      };

      const handleMouseLeave = () => {
        gsap.to(cardElement, {
          rotateX: 0,
          rotateY: 0,
          duration: 0.5,
          ease: 'power2.out',
        });

        if (glowElement) {
          gsap.to(glowElement, {
            opacity: 0,
            duration: 0.3,
          });
        }
      };

      cardElement.addEventListener('mousemove', handleMouseMove);
      cardElement.addEventListener('mouseleave', handleMouseLeave);

      cleanupFunctions.push(() => {
        cardElement.removeEventListener('mousemove', handleMouseMove);
        cardElement.removeEventListener('mouseleave', handleMouseLeave);
      });
    });

    return () => {
      cleanupFunctions.forEach((cleanup) => cleanup());
    };
  }, [glow, glowColor, tiltStrength]);

  const enhancedChildren = Children.map(children, (child) => {
    if (isValidElement(child)) {
      return cloneElement(child as React.ReactElement<{ glow?: boolean }>, { glow });
    }
    return child;
  });

  return (
    <div
      ref={containerRef}
      className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ${className}`}
      style={{
        perspective: '1000px',
        ...style,
      }}
    >
      {enhancedChildren}
    </div>
  );
};

export const MagicBentoItem = ({
  children,
  className = '',
  style,
  colSpan = 1,
  rowSpan = 1,
  glow = true,
}: MagicBentoItemProps & { glow?: boolean }) => {
  const colSpanClass = {
    1: 'col-span-1',
    2: 'md:col-span-2',
    3: 'lg:col-span-3',
  }[colSpan];

  const rowSpanClass = {
    1: 'row-span-1',
    2: 'row-span-2',
  }[rowSpan];

  return (
    <div
      className={`magic-bento-item relative overflow-hidden rounded-2xl bg-white backdrop-blur-sm border border-slate-200 shadow-lg ${colSpanClass} ${rowSpanClass} ${className}`}
      style={{
        transformStyle: 'preserve-3d',
        ...style,
      }}
    >
      {glow && (
        <div
          className="bento-glow absolute inset-0 pointer-events-none opacity-0 z-10"
          style={{
            background: 'transparent',
          }}
        />
      )}
      <div className="relative z-0 h-full w-full p-6">
        {children}
      </div>
    </div>
  );
};

export default MagicBento;
