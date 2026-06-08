/**
 * @file SignatureBadge.tsx
 * @description Displays cosign signature status using Ant Design Tag.
 *              - Green: Signed & Verified
 *              - Orange: Signed only
 *              - Red: Not Signed
 *
 * @dependencies antd, @ant-design/icons
 * @relatedFiles ../pages/GoldImages/index.tsx, ../pages/AppImages/index.tsx
 */
import { Tag, Tooltip } from 'antd';
import { SafetyCertificateOutlined, CheckCircleOutlined } from '@ant-design/icons';

interface SignatureBadgeProps {
  /** Whether the image is signed (new API) */
  signed?: boolean;
  /** Whether the signature is verified (new API) */
  verified?: boolean;
  // ── Backward-compatible (old) props ──────────────────────────────────────
  /** @deprecated Use `signed` instead */
  isSigned?: boolean;
  /** @deprecated Raw cosign signature string (shown in tooltip) */
  signature?: string | null;
}

export function SignatureBadge({
  signed,
  verified,
  isSigned,
  signature,
}: SignatureBadgeProps) {
  const effectiveSigned = signed ?? isSigned ?? false;
  const effectiveVerified = verified ?? false;

  if (effectiveSigned && effectiveVerified) {
    return (
      <Tooltip title={signature ? `Signed & Verified: ${signature}` : 'Image is signed and verified'}>
        <Tag icon={<SafetyCertificateOutlined />} color="success">
          Signed & Verified
        </Tag>
      </Tooltip>
    );
  }

  if (effectiveSigned) {
    return (
      <Tooltip title={signature ? `Signed: ${signature}` : 'Image is signed with cosign'}>
        <Tag icon={<CheckCircleOutlined />} color="warning">
          Signed
        </Tag>
      </Tooltip>
    );
  }

  return (
    <Tooltip title="Image is not signed">
      <Tag color="error">Not Signed</Tag>
    </Tooltip>
  );
}

export default SignatureBadge;
