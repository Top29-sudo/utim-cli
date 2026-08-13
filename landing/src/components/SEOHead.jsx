import React, { useEffect } from 'react';

/**
 * Dynamic SEO Head Manager & JSON-LD Structured Data Injector
 * Guarantees 100% crawlability for Search Engines and AI Web Crawlers.
 */
export default function SEOHead({
  title = "UTIM AI — Autonomous Terminal AI Agent & Creators Ecosystem",
  description = "UTIM AI v2.1.3 is an autonomous, high-agency CLI AI coding agent and Creators Ecosystem marketplace for terminal-first developers.",
  canonical = "https://utim.dev/",
  ogImage = "https://utim.dev/1.png",
  schemaType = "SoftwareApplication",
  schemaData = null,
}) {
  useEffect(() => {
    // 1. Update Title
    document.title = title;

    // 2. Helper to set or update meta tag
    const setMeta = (name, value, attr = 'name') => {
      let el = document.querySelector(`meta[${attr}="${name}"]`);
      if (!el) {
        el = document.createElement('meta');
        el.setAttribute(attr, name);
        document.head.appendChild(el);
      }
      el.setAttribute('content', value);
    };

    // Standard Meta Tags
    setMeta('description', description);
    setMeta('robots', 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1');
    setMeta('googlebot', 'index, follow');

    // Open Graph / Facebook
    setMeta('og:title', title, 'property');
    setMeta('og:description', description, 'property');
    setMeta('og:url', canonical, 'property');
    setMeta('og:image', ogImage, 'property');
    setMeta('og:type', 'website', 'property');
    setMeta('og:site_name', 'UTIM AI', 'property');

    // Twitter Card
    setMeta('twitter:card', 'summary_large_image');
    setMeta('twitter:title', title);
    setMeta('twitter:description', description);
    setMeta('twitter:image', ogImage);

    // Canonical Link
    let linkCanonical = document.querySelector('link[rel="canonical"]');
    if (!linkCanonical) {
      linkCanonical = document.createElement('link');
      linkCanonical.setAttribute('rel', 'canonical');
      document.head.appendChild(linkCanonical);
    }
    linkCanonical.setAttribute('href', canonical);

    // 3. Inject JSON-LD Schema.org Structured Data
    let scriptJsonLd = document.getElementById('json-ld-schema');
    if (!scriptJsonLd) {
      scriptJsonLd = document.createElement('script');
      scriptJsonLd.id = 'json-ld-schema';
      scriptJsonLd.type = 'application/ld+json';
      document.head.appendChild(scriptJsonLd);
    }

    const defaultSchema = {
      "@context": "https://schema.org",
      "@type": schemaType,
      "name": "UTIM AI CLI",
      "url": canonical,
      "description": description,
      "operatingSystem": "Windows, macOS, Linux, Android Termux",
      "applicationCategory": "DeveloperApplication",
      "offers": {
        "@type": "AggregateOffer",
        "priceCurrency": "USD",
        "lowPrice": "0",
        "highPrice": "49",
        "offerCount": "3"
      }
    };

    scriptJsonLd.text = JSON.stringify(schemaData || defaultSchema);
  }, [title, description, canonical, ogImage, schemaType, schemaData]);

  return null;
}
