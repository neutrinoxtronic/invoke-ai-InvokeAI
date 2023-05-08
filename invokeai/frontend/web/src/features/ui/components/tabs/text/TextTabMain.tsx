import { Box, Flex } from '@chakra-ui/react';
import CurrentImageDisplay from 'features/gallery/components/CurrentImageDisplay';
import ProgressImagePreview from 'features/parameters/components/ProgressImagePreview';

const TextTabMain = () => {
  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        height: '100%',
        borderRadius: 'base',
        // bg: 'base.850',
      }}
    >
      <Flex
        sx={{
          // p: 2,
          width: '100%',
          height: '100%',
        }}
      >
        <CurrentImageDisplay />
      </Flex>
    </Box>
  );
};

export default TextTabMain;