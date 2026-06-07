/**
 * @file SignatureBadge.tsx
 * @description Displays cosign signature status:
 *              - 🔒 Green lock: signed
 *              - 🔓 Gray lock: not signed
 * @dependencies @mui/material, @mui/icons-material
 * @relatedFiles ../pages/GoldImages/index.tsx, ../pages/AppImages/index.tsx
 */
import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';

interface SignatureBadgeProps {
  isSigned: boolean;
  signature?: string | null;
}

export const SignatureBadge: React.FC<SignatureBadgeProps> = ({
  isSigned,
  signature,
}) => {
  if (isSigned) {
    return (
      <Tooltip title={signature ? `Signed: ${signature}` : 'Image is signed with cosign'}>
        <Chip
          label="Signed"
          size="small"
          color="success"
          icon={<LockIcon />}
        />
      </Tooltip>
    );
  }

  return (
    <Tooltip title="Image is not signed">
      <Chip
        label="Unsigned"
        size="small"
        color="default"
        icon={<LockOpenIcon />}
      />
    </Tooltip>
  );
};
