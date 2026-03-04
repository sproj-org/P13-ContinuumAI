"use client";

import { useScroll, useTransform, motion, MotionValue, AnimatePresence } from "motion/react";
import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import Lenis from "lenis";

interface ScrollStackProps {
  cards: React.ReactNode[];
  cardHeight?: number;
  stickyStart?: number;
  cardGap?: number;
  onActiveIndexChange?: (index: number) => void;
}

export const ScrollStack: React.FC<ScrollStackProps> = ({
  cards,
  cardHeight = 500,
  stickyStart = 10,
  cardGap = 30,
  onActiveIndexChange,
}) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const totalCards = cards.length;
  const totalScrollableBlocks = totalCards - 1;
  const perBlockProgress = 1 / totalScrollableBlocks;

  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  useEffect(() => {
    const lenis = new Lenis({
      lerp: 0.1,
      smoothWheel: true,
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }

    requestAnimationFrame(raf);

    return () => {
      lenis.destroy();
    };
  }, []);

  useEffect(() => {
    const unsubscribe = scrollYProgress.on("change", (progress) => {
      let newIndex = 0;
      for (let i = 0; i < totalScrollableBlocks; i++) {
        if (progress >= perBlockProgress * i && progress < perBlockProgress * (i + 1)) {
          newIndex = i;
          break;
        }
        if (progress >= perBlockProgress * totalScrollableBlocks) {
          newIndex = totalScrollableBlocks;
        }
      }
      setActiveIndex(newIndex);
    });

    return () => unsubscribe();
  }, [scrollYProgress, perBlockProgress, totalScrollableBlocks]);

  useEffect(() => {
    onActiveIndexChange?.(activeIndex);
  }, [activeIndex, onActiveIndexChange]);

  return (
    <div
      ref={containerRef}
      className="relative isolate w-full"
      style={{
        height: `${totalCards * 100}vh`,
      }}
    >
      <div
        style={{
          position: "sticky",
          top: stickyStart,
          height: cardHeight,
          overflow: "hidden",
        }}
      >
        <AnimatePresence initial={false}>
          {cards.map((card, index) => (
            <Card
              key={index}
              index={index}
              activeIndex={activeIndex}
              totalCards={totalCards}
              scrollYProgress={scrollYProgress}
              perBlockProgress={perBlockProgress}
              cardHeight={cardHeight}
              cardGap={cardGap}
            >
              {card}
            </Card>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

interface CardProps {
  children: React.ReactNode;
  index: number;
  activeIndex: number;
  totalCards: number;
  scrollYProgress: MotionValue<number>;
  perBlockProgress: number;
  cardHeight: number;
  cardGap: number;
}

const Card = React.memo<CardProps>(({
  children,
  index,
  activeIndex,
  totalCards,
  scrollYProgress,
  perBlockProgress,
  cardHeight,
  cardGap,
}) => {
  const cardAnimationStart = index * perBlockProgress;
  const cardAnimationEnd = (index + 1) * perBlockProgress;

  const yOffset = useTransform(
    scrollYProgress,
    [cardAnimationStart, cardAnimationEnd],
    [cardHeight + cardGap, 0]
  );

  const isPreviousCard = index < activeIndex;
  const isActive = index === activeIndex;
  const isFutureCard = index > activeIndex;

  const shouldShow = !isPreviousCard;
  const zIndex = totalCards - index;

  const stackOffset = useMemo(() => {
    const offsetFromActive = index - activeIndex;
    if (offsetFromActive > 0) {
      const maxOffset = 20;
      const maxVisible = 3;
      if (offsetFromActive <= maxVisible) {
        return offsetFromActive * (maxOffset / maxVisible);
      }
    }
    return 0;
  }, [index, activeIndex]);

  const getBoxShadow = useCallback(() => {
    if (isActive) {
      return "0 25px 50px -12px rgba(0, 0, 0, 0.5)";
    }
    if (isFutureCard) {
      return "0 10px 30px -10px rgba(0, 0, 0, 0.3)";
    }
    return "none";
  }, [isActive, isFutureCard]);

  if (!shouldShow) return null;

  return (
    <motion.div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        y: isActive ? yOffset : stackOffset,
        zIndex,
        height: cardHeight,
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div
        style={{
          height: "100%",
          width: "100%",
          borderRadius: "12px",
          overflow: "hidden",
          boxShadow: getBoxShadow(),
        }}
      >
        {children}
      </div>
    </motion.div>
  );
});

Card.displayName = "Card";

export default ScrollStack;
