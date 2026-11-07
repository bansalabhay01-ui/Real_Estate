// Small inline icons (no icon library needed). Decorative by default: give a label where they stand alone.
function Icon({ children, className = "size-4", label }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? "img" : undefined}
    >
      {children}
    </svg>
  );
}

export const IconAlert = (props) => (
  <Icon {...props}>
    <path d="M12 3 2 20h20L12 3Z" />
    <path d="M12 10v4M12 17.5v.01" />
  </Icon>
);

export const IconEnquiry = (props) => (
  <Icon {...props}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </Icon>
);

export const IconChat = (props) => (
  <Icon {...props}>
    <path d="M4 5h16v11H9l-5 4V5Z" />
  </Icon>
);

export const IconClose = (props) => (
  <Icon {...props}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
);

export const IconBack = (props) => (
  <Icon {...props}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Icon>
);

export const IconDownload = (props) => (
  <Icon {...props}>
    <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
  </Icon>
);

export const IconSend = (props) => (
  <Icon {...props}>
    <path d="M4 12 20 4l-6 16-3-7-7-1Z" />
  </Icon>
);

export const IconCheck = (props) => (
  <Icon {...props}>
    <path d="m5 12 5 5 9-10" />
  </Icon>
);

export const IconBot = (props) => (
  <Icon {...props}>
    <rect x="4" y="8" width="16" height="11" rx="2" />
    <path d="M12 4v4M9 13v.01M15 13v.01M9.5 16h5" />
  </Icon>
);

export const IconBan = (props) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m6 6 12 12" />
  </Icon>
);

export const IconEye = (props) => (
  <Icon {...props}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="2.5" />
  </Icon>
);

// Intent strength: 1, 2 or 3 bars (Cold, Warm, Hot), so the order shows without relying on colour.
export function IconStrength({ level, className = "size-4" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {[0, 1, 2].map((step) => (
        <rect
          key={step}
          x={4 + step * 6}
          y={16 - step * 5}
          width="4"
          height={4 + step * 5}
          rx="1"
          fill="currentColor"
          opacity={step < level ? 1 : 0.25}
        />
      ))}
    </svg>
  );
}

// A lab flask: marks test sessions opened through a tester link.
export const IconTest = (props) => (
  <Icon {...props}>
    <path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3" />
    <path d="M7 15h10" />
  </Icon>
);

// The brand mark: a plan square with two inner walls.
export const PlanMark = ({ className = "size-7" }) => (
  <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
    <rect width="32" height="32" rx="6" fill="#1d4f91" />
    <path d="M7 7h18v18H7zM7 17h10M17 7v18" fill="none" stroke="#e6effa" strokeWidth="2.2" />
  </svg>
);
