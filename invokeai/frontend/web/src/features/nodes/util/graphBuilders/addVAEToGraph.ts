import { RootState } from 'app/store/store';
import { NonNullableGraph } from 'features/nodes/types/types';
import { modelIdToVAEModelField } from '../modelIdToVAEModelField';
import {
  IMAGE_TO_LATENTS,
  INPAINT,
  LATENTS_TO_IMAGE,
  MAIN_MODEL_LOADER,
  VAE_LOADER,
} from './constants';

export const addVAEToGraph = (
  graph: NonNullableGraph,
  state: RootState
): void => {
  const { vae: vaeId } = state.generation;
  const vae_model = modelIdToVAEModelField(vaeId);

  if (vaeId !== 'auto') {
    graph.nodes[VAE_LOADER] = {
      type: 'vae_loader',
      id: VAE_LOADER,
      vae_model,
    };
  }

  if (
    graph.id === 'text_to_image_graph' ||
    graph.id === 'image_to_image_graph'
  ) {
    graph.edges.push({
      source: {
        node_id: vaeId === 'auto' ? MAIN_MODEL_LOADER : VAE_LOADER,
        field: 'vae',
      },
      destination: {
        node_id: LATENTS_TO_IMAGE,
        field: 'vae',
      },
    });
  }

  if (graph.id === 'image_to_image_graph') {
    graph.edges.push({
      source: {
        node_id: vaeId === 'auto' ? MAIN_MODEL_LOADER : VAE_LOADER,
        field: 'vae',
      },
      destination: {
        node_id: IMAGE_TO_LATENTS,
        field: 'vae',
      },
    });
  }

  if (graph.id === 'inpaint_graph') {
    graph.edges.push({
      source: {
        node_id: vaeId === 'auto' ? MAIN_MODEL_LOADER : VAE_LOADER,
        field: 'vae',
      },
      destination: {
        node_id: INPAINT,
        field: 'vae',
      },
    });
  }
};
