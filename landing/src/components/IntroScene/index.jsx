import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './IntroScene.css';

const IntroScene = ({ onComplete }) => {
  const [text, setText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const [phase, setPhase] = useState(0); // 0: typing, 1: enter hit, 2: booting

  const command = "utim";

  useEffect(() => {
    // Blinking cursor
    const cursorInterval = setInterval(() => {
      setShowCursor(prev => !prev);
    }, 500);
    return () => clearInterval(cursorInterval);
  }, []);

  useEffect(() => {
    if (phase === 0) {
      let i = 0;
      const typeInterval = setInterval(() => {
        setText(command.slice(0, i));
        i++;
        if (i > command.length) {
          clearInterval(typeInterval);
          setTimeout(() => setPhase(1), 500);
        }
      }, 100);
      return () => clearInterval(typeInterval);
    } else if (phase === 1) {
      // Simulate enter key hit
      setTimeout(() => setPhase(2), 200);
    } else if (phase === 2) {
      // Show boot sequence, then complete
      setTimeout(() => {
        onComplete();
      }, 2500);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  return (
    <motion.div 
      className="intro-scene-container"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 1.05 }}
      transition={{ duration: 0.8, ease: "easeInOut" }}
    >
      <div className="intro-terminal">
        {phase < 2 ? (
          <div className="intro-prompt-line">
            <span className="intro-path">PS C:\projects\utim&gt;</span>
            <span className="intro-cmd">{text}</span>
            {showCursor && <span className="intro-cursor">█</span>}
          </div>
        ) : (
          <div className="intro-boot-sequence">
            <div className="intro-prompt-line">
              <span className="intro-path">PS C:\projects\utim&gt;</span>
              <span className="intro-cmd">{command}</span>
            </div>
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
              className="intro-log"
            >
              <div style={{ color: '#00f0ff' }}>[SYSTEM] Initiating U.T.I.M Core...</div>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} style={{ color: '#ccc' }}>Loading neural matrices [||||||||||] 100%</motion.div>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }} style={{ color: '#ccc' }}>Establishing secure connection to OpenRouter...</motion.div>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2 }} style={{ color: '#10b981' }}>Connection established.</motion.div>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }} style={{ color: '#f9f1a5' }}>Mounting virtual workspace...</motion.div>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 2.0 }} style={{ color: '#00f0ff', fontWeight: 'bold', marginTop: '10px' }}>U.T.I.M Agent Ready. Handing over control.</motion.div>
            </motion.div>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default IntroScene;
