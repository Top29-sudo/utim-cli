import React, { useEffect, useRef } from 'react';

/**
 * MouseEffects — adds mouse interactivity to the whole site:
 *  - Custom cursor (dot + trailing ring)
 *  - Magnetic buttons (elements with .clean-magnetic class)
 *  - 3D tilt cards (elements with .clean-tilt class)
 *  - Hover detection for the cursor ring
 */
const MouseEffects = () => {
  const dotRef = useRef(null);
  const ringRef = useRef(null);

  useEffect(() => {
    const dot = dotRef.current;
    const ring = ringRef.current;
    if (!dot || !ring) return;

    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let ringX = mouseX;
    let ringY = mouseY;
    let raf = null;

    const onMouseMove = (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      dot.style.left = `${mouseX}px`;
      dot.style.top = `${mouseY}px`;

      // Detect hovering interactive elements
      const target = e.target;
      const interactive = target.closest(
        'a, button, .clean-cta-btn, .clean-cta-secondary, .clean-nav-link, .clean-feature-card, .clean-card, input, [role="button"]'
      );
      ring.classList.toggle('is-hovering', !!interactive);
    };

    const onMouseDown = () => ring.classList.add('is-down');
    const onMouseUp = () => ring.classList.remove('is-down');

    // Smooth ring follow (lerp)
    const animateRing = () => {
      ringX += (mouseX - ringX) * 0.15;
      ringY += (mouseY - ringY) * 0.15;
      ring.style.left = `${ringX}px`;
      ring.style.top = `${ringY}px`;
      raf = requestAnimationFrame(animateRing);
    };
    raf = requestAnimationFrame(animateRing);

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mouseup', onMouseUp);

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('mouseup', onMouseUp);
      cancelAnimationFrame(raf);
    };
  }, []);

  // Magnetic buttons
  useEffect(() => {
    const magnets = document.querySelectorAll('.clean-magnetic');
    const onMove = (e) => {
      magnets.forEach((el) => {
        const rect = el.getBoundingClientRect();
        const x = e.clientX - (rect.left + rect.width / 2);
        const y = e.clientY - (rect.top + rect.height / 2);
        el.style.transform = `translate(${x * 0.25}px, ${y * 0.25}px)`;
      });
    };
    const onLeave = () => {
      magnets.forEach((el) => {
        el.style.transform = 'translate(0, 0)';
      });
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseleave', onLeave);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  // 3D tilt cards
  useEffect(() => {
    const tiltEls = document.querySelectorAll('.clean-tilt');
    const onMove = (e) => {
      tiltEls.forEach((el) => {
        const rect = el.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width;
        const py = (e.clientY - rect.top) / rect.height;
        const rx = (0.5 - py) * 10;
        const ry = (px - 0.5) * 10;
        el.style.transform = `perspective(800px) rotateX(${rx}deg) rotateY(${ry}deg)`;
      });
    };
    const onLeave = () => {
      tiltEls.forEach((el) => {
        el.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg)';
      });
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseleave', onLeave);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  return (
    <>
      <div className="clean-cursor-dot" ref={dotRef} />
      <div className="clean-cursor-ring" ref={ringRef} />
    </>
  );
};

export default MouseEffects;
