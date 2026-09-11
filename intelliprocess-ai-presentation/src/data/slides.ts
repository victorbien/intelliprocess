export type SlideMeta = {
  id: string;
  title: string;
  route: string;
  label: string;
};

export const slides: SlideMeta[] = [
  { id: 'cover', title: 'IntelliProcess AI', route: '/presentation', label: '01' },
  { id: 'problem', title: 'The Problem', route: '/presentation/problem', label: '02' },
  { id: 'transformation', title: 'Transformation', route: '/presentation/transformation', label: '03' },
  { id: 'solution', title: 'IntelliProcess AI', route: '/presentation/solution', label: '04' },
  { id: 'how-it-works', title: 'How It Works', route: '/presentation/how-it-works', label: '05' },
  { id: 'document-processing', title: 'Document Intelligence', route: '/presentation/document-processing', label: '06' },
  { id: 'three-way-matching', title: 'Three-Way Matching', route: '/presentation/three-way-matching', label: '07' },
  { id: 'exceptions', title: 'Human Review', route: '/presentation/exceptions', label: '08' },
  { id: 'dashboard', title: 'AP Operations Dashboard', route: '/presentation/dashboard', label: '09' },
  { id: 'ask-your-records', title: 'Ask Your Records', route: '/presentation/ask-your-records', label: '10' },
  { id: 'platform', title: 'One Platform', route: '/presentation/platform', label: '11' },
  { id: 'architecture', title: 'AWS Architecture', route: '/presentation/architecture', label: '12' },
  { id: 'security', title: 'Security & Access', route: '/presentation/security', label: '13' },
  { id: 'business-value', title: 'Business Value', route: '/presentation/business-value', label: '14' },
  { id: 'demo', title: 'Product Demo', route: '/presentation/demo', label: '15' },
  { id: 'closing', title: 'Closing', route: '/presentation/closing', label: '16' },
];

export const slideMap = Object.fromEntries(slides.map((slide) => [slide.route, slide]));
