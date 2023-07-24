import json
import logging

import datasets
import diffusers
import transformers
from accelerate import Accelerator
from accelerate.logging import MultiProcessAdapter, get_logger
from accelerate.utils import ProjectConfiguration, set_seed
from diffusers import AutoencoderKL, DDPMScheduler, UNet2DConditionModel
from transformers import CLIPTextModel, CLIPTokenizer

from invokeai.app.services.config import InvokeAIAppConfig
from invokeai.app.services.model_manager_service import ModelManagerService
from invokeai.backend.model_management.models.base import SubModelType
from invokeai.backend.training.lora.lora_training_config import (
    LoraTrainingConfig,
)


def _initialize_accelerator(train_config: LoraTrainingConfig) -> Accelerator:
    """Configure Hugging Face accelerate and return an Accelerator.

    Args:
        train_config (LoraTrainingConfig): LoRA training configuration.

    Returns:
        Accelerator
    """
    accelerator_project_config = ProjectConfiguration(
        project_dir=train_config.output_dir,
        logging_dir=train_config.output_dir / "logs",
    )
    return Accelerator(
        project_config=accelerator_project_config,
        gradient_accumulation_steps=train_config.gradient_accumulation_steps,
        mixed_precision=train_config.mixed_precision,
        log_with=train_config.report_to,
    )


def _initialize_logging(accelerator: Accelerator) -> MultiProcessAdapter:
    """Configure logging.

    Returns an accelerate logger with multi-process logging support. Logging is
    configured to be more verbose on the main process. Non-main processes only
    log at error level for Hugging Face libraries (datasets, transformers,
    diffusers).

    Args:
        accelerator (Accelerator): _description_

    Returns:
        MultiProcessAdapter: _description_
    """
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO,
    )
    if accelerator.is_local_main_process:
        datasets.utils.logging.set_verbosity_warning()
        transformers.utils.logging.set_verbosity_warning()
        diffusers.utils.logging.set_verbosity_info()
    else:
        # Only log errors from non-main processes.
        datasets.utils.logging.set_verbosity_error()
        transformers.utils.logging.set_verbosity_error()
        diffusers.utils.logging.set_verbosity_error()

    return get_logger(__name__)


def _load_models(
    app_config: InvokeAIAppConfig,
    train_config: LoraTrainingConfig,
    logger: logging.Logger,
) -> tuple[
    CLIPTokenizer,
    DDPMScheduler,
    CLIPTextModel,
    AutoencoderKL,
    UNet2DConditionModel,
]:
    """Load all models required for training.

    Args:
        app_config (InvokeAIAppConfig): The app config.
        train_config (LoraTrainingConfig): The LoRA training run config.
        logger (logging.Logger): A logger.

    Returns:
        tuple[
            CLIPTokenizer,
            DDPMScheduler,
            CLIPTextModel,
            AutoencoderKL,
            UNet2DConditionModel,
        ]: A tuple of loaded models.
    """
    model_manager = ModelManagerService(app_config, logger)

    known_models = model_manager.model_names()

    model_name = train_config.model.split("/")[-1]

    # Find the first known model that matches model_name. Raise an exception if
    # there is no match.
    model_meta = next(
        (mm for mm in known_models if mm[0].endswith(model_name)), None
    )
    assert model_meta is not None, f"Unknown model: {train_config.model}"

    # Validate that the model is a diffusers model.
    model_info = model_manager.model_info(*model_meta)
    model_format = model_info["model_format"]
    assert model_format == "diffusers", (
        "LoRA training only supports models in the 'diffusers' format."
        f" '{train_config.model}' is in the '{model_format}' format. "
    )

    # Get sub-model info.
    tokenizer_info = model_manager.get_model(
        *model_meta, submodel=SubModelType.Tokenizer
    )
    noise_scheduler_info = model_manager.get_model(
        *model_meta, submodel=SubModelType.Scheduler
    )
    text_encoder_info = model_manager.get_model(
        *model_meta, submodel=SubModelType.TextEncoder
    )
    vae_info = model_manager.get_model(*model_meta, submodel=SubModelType.Vae)
    unet_info = model_manager.get_model(*model_meta, submodel=SubModelType.UNet)

    # Load all models.
    pipeline_args = dict(local_files_only=True)
    tokenizer: CLIPTokenizer = CLIPTokenizer.from_pretrained(
        tokenizer_info.location, subfolder="tokenizer", **pipeline_args
    )
    noise_scheduler: DDPMScheduler = DDPMScheduler.from_pretrained(
        noise_scheduler_info.location, subfolder="scheduler", **pipeline_args
    )
    text_encoder: CLIPTextModel = CLIPTextModel.from_pretrained(
        text_encoder_info.location, subfolder="text_encoder", **pipeline_args
    )
    vae: AutoencoderKL = AutoencoderKL.from_pretrained(
        vae_info.location, subfolder="vae", **pipeline_args
    )
    unet: UNet2DConditionModel = UNet2DConditionModel.from_pretrained(
        unet_info.location, subfolder="unet", **pipeline_args
    )

    return tokenizer, noise_scheduler, text_encoder, vae, unet


def run_lora_training(
    app_config: InvokeAIAppConfig, train_config: LoraTrainingConfig
):
    accelerator = _initialize_accelerator(train_config)
    logger = _initialize_logging(accelerator)

    # Log the accelerator configuration from every process to help with
    # debugging.
    logger.info(accelerator.state, main_process_only=False)

    logger.info("Starting LoRA Training.")
    logger.info(
        f"Configuration:\n{json.dumps(train_config.dict(), indent=2, default=str)}"
    )

    tokenizer, noise_scheduler, text_encoder, vae, unet = _load_models(
        app_config, train_config, logger
    )
