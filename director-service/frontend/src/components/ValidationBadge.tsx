import type { ValidationReport } from '../types';

interface Props {
  report: ValidationReport;
}

export default function ValidationBadge({ report }: Props) {
  const style: React.CSSProperties = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    color: '#fff',
    backgroundColor: report.is_valid ? '#2e7d32' : '#c62828',
  };

  return (
    <span style={style}>
      {report.is_valid ? 'VALID' : 'INVALID'}
      {report.warnings.length > 0 && ` (${report.warnings.length} warnings)`}
      {report.errors.length > 0 && ` (${report.errors.length} errors)`}
    </span>
  );
}
