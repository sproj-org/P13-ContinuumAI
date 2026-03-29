"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export type LogoItem =
  | {
      node: React.ReactNode;
      href?: string;
      title?: string;
      ariaLabel?: string;
    }
  | {
      src: string;
      alt?: string;
      href?: string;
      title?: string;
      srcSet?: string;
      sizes?: string;
      width?: number;
      height?: number;
    };

export interface LogoLoopProps {
  logos: LogoItem[];
  speed?: number;
  direction?: 'left' | 'right' | 'up' | 'down';
  width?: number | string;
  logoHeight?: number;
  gap?: number;
  pauseOnHover?: boolean;
  hoverSpeed?: number;
  fadeOut?: boolean;
  fadeOutColor?: string;
  scaleOnHover?: boolean;
  renderItem?: (item: LogoItem, key: React.Key) => React.ReactNode;
  ariaLabel?: string;
  className?: string;
  style?: React.CSSProperties;
}

const ANIMATION_CONFIG = {
  SMOOTH_TAU: 0.25,
  MIN_COPIES: 2,
  COPY_HEADROOM: 2
} as const;

const toCssLength = (value?: number | string): string | undefined =>
  typeof value === 'number' ? `${value}px` : (value ?? undefined);

const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(' ');

const useResizeObserver = (
  callback: () => void,
  elements: Array<React.RefObject<Element | null>>,
  dependencies: React.DependencyList
) => {
  useEffect(() => {
    if (!window.ResizeObserver) {
      const handleResize = () => callback();
      window.addEventListener('resize', handleResize);
      callback();
      return () => window.removeEventListener('resize', handleResize);
    }

    const observers = elements.map(ref => {
      if (!ref.current) return null;
      const observer = new ResizeObserver(callback);
      observer.observe(ref.current);
      return observer;
    });

    callback();

    return () => {
      observers.forEach(observer => observer?.disconnect());
    };
  }, dependencies);
};

const useImageLoader = (
  seqRef: React.RefObject<HTMLUListElement | null>,
  onLoad: () => void,
  dependencies: React.DependencyList
) => {
  useEffect(() => {
    const images = seqRef.current?.querySelectorAll('img') ?? [];

    if (images.length === 0) {
      onLoad();
      return;
    }

    let remainingImages = images.length;
    const handleImageLoad = () => {
      remainingImages -= 1;
      if (remainingImages === 0) onLoad();
    };

    images.forEach(img => {
      const htmlImg = img as HTMLImageElement;
      if (htmlImg.complete) {
        handleImageLoad();
      } else {
        img.addEventListener('load', handleImageLoad);
        img.addEventListener('error', handleImageLoad);
      }
    });

    return () => {
      images.forEach(img => {
        img.removeEventListener('load', handleImageLoad);
        img.removeEventListener('error', handleImageLoad);
      });
    };
  }, dependencies);
};

const useAnimationLoop = (
  trackRef: React.RefObject<HTMLDivElement | null>,
  targetVelocity: number,
  seqWidth: number,
  seqHeight: number,
  isHovered: boolean,
  hoverSpeed: number | undefined,
  isVertical: boolean
) => {
  const rafRef = useRef<number | null>(null);
  const lastTimestampRef = useRef<number | null>(null);
  const offsetRef = useRef(0);
  const velocityRef = useRef(0);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const seqSize = isVertical ? seqHeight : seqWidth;

    if (seqSize > 0) {
      offsetRef.current = ((offsetRef.current % seqSize) + seqSize) % seqSize;
      const transformValue = isVertical
        ? `translate3d(0, ${-offsetRef.current}px, 0)`
        : `translate3d(${-offsetRef.current}px, 0, 0)`;
      track.style.transform = transformValue;
    }

    if (prefersReduced) {
      track.style.transform = isVertical ? 'translate3d(0, 0, 0)' : 'translate3d(0, 0, 0)';
      return () => {};
    }

    const animate = (timestamp: number) => {
      if (lastTimestampRef.current === null) {
        lastTimestampRef.current = timestamp;
      }

      const deltaTime = Math.max(0, timestamp - lastTimestampRef.current) / 1000;
      lastTimestampRef.current = timestamp;

      const target = isHovered && hoverSpeed !== undefined ? hoverSpeed : targetVelocity;

      const easingFactor = 1 - Math.exp(-deltaTime / ANIMATION_CONFIG.SMOOTH_TAU);
      velocityRef.current += (target - velocityRef.current) * easingFactor;

      if (seqSize > 0) {
        offsetRef.current += velocityRef.current * deltaTime;
        offsetRef.current = ((offsetRef.current % seqSize) + seqSize) % seqSize;
        const transformValue = isVertical
          ? `translate3d(0, ${-offsetRef.current}px, 0)`
          : `translate3d(${-offsetRef.current}px, 0, 0)`;
        track.style.transform = transformValue;
      }

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      lastTimestampRef.current = null;
    };
  }, [trackRef, targetVelocity, seqWidth, seqHeight, isHovered, hoverSpeed, isVertical]);
};

export const LogoLoop = React.memo<LogoLoopProps>(
  ({
    logos,
    speed = 120,
    direction = 'left',
    width = '100%',
    logoHeight = 28,
    gap = 32,
    pauseOnHover,
    hoverSpeed,
    fadeOut = false,
    fadeOutColor = 'white',
    scaleOnHover = false,
    renderItem,
    ariaLabel = 'Partner logos',
    className,
    style
  }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const trackRef = useRef<HTMLDivElement>(null);
    const seqRef = useRef<HTMLUListElement>(null);

    const [seqWidth, setSeqWidth] = useState<number>(0);
    const [seqHeight, setSeqHeight] = useState<number>(0);
    const [copyCount, setCopyCount] = useState<number>(ANIMATION_CONFIG.MIN_COPIES);
    const [isHovered, setIsHovered] = useState<boolean>(false);

    const effectiveHoverSpeed = useMemo(() => {
      if (hoverSpeed !== undefined) return hoverSpeed;
      if (pauseOnHover === true) return 0;
      return undefined;
    }, [hoverSpeed, pauseOnHover]);

    const isVertical = direction === 'up' || direction === 'down';

    const targetVelocity = useMemo(() => {
      const magnitude = Math.abs(speed);
      const directionMultiplier = direction === 'right' || direction === 'down' ? -1 : 1;
      const speedMultiplier = isVertical ? 0.5 : 1;
      return magnitude * directionMultiplier * speedMultiplier;
    }, [speed, direction, isVertical]);

    const updateDimensions = useCallback(() => {
      const seq = seqRef.current;
      const container = containerRef.current;
      if (!seq || !container) return;

      const seqRect = seq.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      setSeqWidth(seqRect.width);
      setSeqHeight(seqRect.height);

      const containerSize = isVertical ? containerRect.height : containerRect.width;
      const seqSize = isVertical ? seqRect.height : seqRect.width;

      if (seqSize > 0) {
        const needed = Math.ceil(containerSize / seqSize) + ANIMATION_CONFIG.COPY_HEADROOM;
        setCopyCount(Math.max(ANIMATION_CONFIG.MIN_COPIES, needed));
      }
    }, [isVertical]);

    useResizeObserver(updateDimensions, [containerRef, seqRef], [logos, gap, logoHeight, isVertical]);

    useImageLoader(seqRef, updateDimensions, [logos, gap, logoHeight, isVertical]);

    useAnimationLoop(trackRef, targetVelocity, seqWidth, seqHeight, isHovered, effectiveHoverSpeed, isVertical);

    const handleMouseEnter = useCallback(() => {
      if (effectiveHoverSpeed !== undefined) setIsHovered(true);
    }, [effectiveHoverSpeed]);
    const handleMouseLeave = useCallback(() => {
      if (effectiveHoverSpeed !== undefined) setIsHovered(false);
    }, [effectiveHoverSpeed]);

    const renderLogoItem = useCallback(
      (item: LogoItem, index: number, listIndex: number) => {
        const key = `${listIndex}-${index}`;

        if (renderItem) {
          return (
            <li key={key} style={{ display: 'flex', alignItems: 'center' }}>
              {renderItem(item, key)}
            </li>
          );
        }

        const isNode = 'node' in item;
        const content = isNode ? (
          <span
            style={{ height: logoHeight, display: 'flex', alignItems: 'center', fontSize: logoHeight }}
            className={scaleOnHover ? 'transition-transform hover:scale-110' : ''}
          >
            {item.node}
          </span>
        ) : (
          <img
            src={item.src}
            alt={item.alt || ''}
            srcSet={item.srcSet}
            sizes={item.sizes}
            width={item.width}
            height={item.height}
            style={{ height: logoHeight, width: 'auto', objectFit: 'contain' }}
            className={scaleOnHover ? 'transition-transform hover:scale-110' : ''}
            loading="lazy"
          />
        );

        const href = item.href;
        const title = item.title;

        return (
          <li key={key} style={{ display: 'flex', alignItems: 'center' }}>
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                title={title}
                aria-label={isNode ? (item as { ariaLabel?: string }).ariaLabel || title : item.alt || title}
                style={{ display: 'flex', alignItems: 'center' }}
              >
                {content}
              </a>
            ) : (
              <span title={title} style={{ display: 'flex', alignItems: 'center' }}>
                {content}
              </span>
            )}
          </li>
        );
      },
      [logoHeight, renderItem, scaleOnHover]
    );

    const logoLists = useMemo(
      () =>
        Array.from({ length: copyCount }, (_, listIndex) => (
          <ul
            key={listIndex}
            ref={listIndex === 0 ? seqRef : undefined}
            style={{
              display: 'flex',
              flexDirection: isVertical ? 'column' : 'row',
              alignItems: 'center',
              gap: gap,
              listStyle: 'none',
              margin: 0,
              padding: 0
            }}
            aria-hidden={listIndex > 0}
          >
            {logos.map((logo, idx) => renderLogoItem(logo, idx, listIndex))}
          </ul>
        )),
      [copyCount, gap, isVertical, logos, renderLogoItem]
    );

    const containerStyle = useMemo(
      () => ({
        ...style,
        width: toCssLength(width),
        overflow: 'hidden',
        position: 'relative' as const
      }),
      [style, width]
    );

    return (
      <div
        ref={containerRef}
        className={cx('logo-loop', className)}
        style={containerStyle}
        role="region"
        aria-label={ariaLabel}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {fadeOut && (
          <>
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: isVertical ? '100%' : '80px',
                height: isVertical ? '80px' : '100%',
                background: `linear-gradient(${isVertical ? 'to bottom' : 'to right'}, ${fadeOutColor}, transparent)`,
                zIndex: 10,
                pointerEvents: 'none'
              }}
            />
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                right: 0,
                width: isVertical ? '100%' : '80px',
                height: isVertical ? '80px' : '100%',
                background: `linear-gradient(${isVertical ? 'to top' : 'to left'}, ${fadeOutColor}, transparent)`,
                zIndex: 10,
                pointerEvents: 'none'
              }}
            />
          </>
        )}
        <div
          ref={trackRef}
          style={{
            display: 'flex',
            flexDirection: isVertical ? 'column' : 'row',
            gap: gap,
            willChange: 'transform'
          }}
        >
          {logoLists}
        </div>
      </div>
    );
  }
);

LogoLoop.displayName = 'LogoLoop';

export default LogoLoop;
