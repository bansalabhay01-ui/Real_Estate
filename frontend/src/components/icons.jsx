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

// The brand mark: a plan square with two inner walls.
export const PlanMark = ({ className = "size-7" }) => (
  <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
    <rect width="32" height="32" rx="6" fill="#1d4f91" />
    <path d="M7 7h18v18H7zM7 17h10M17 7v18" fill="none" stroke="#e6effa" strokeWidth="2.2" />
  </svg>
);
