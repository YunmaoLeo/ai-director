interface Props {
  data: unknown;
  maxHeight?: number;
}

export default function JsonViewer({ data, maxHeight = 400 }: Props) {
  return (
    <pre
      style={{
        background: '#0d1117',
        color: '#c9d1d9',
        padding: 12,
        borderRadius: 6,
        fontSize: 11,
        fontFamily: 'monospace',
        overflow: 'auto',
        maxHeight,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
