"""Fine-tuning Qwen 2.5 3B with Unsloth + QLoRA.

This script is designed to run on Google Colab with a free T4 GPU.
Install Unsloth first:  pip install unsloth

Dataset format (JSONL):
    {"messages": [
        {"role": "system", "content": "Ты — эмпатичный коуч..."},
        {"role": "user", "content": "Я сорвался и съел торт..."},
        {"role": "assistant", "content": "Я понимаю, это бывает..."}
    ]}

Usage:
    python scripts/fine_tune.py --dataset data/fine_tune/mi_dataset.jsonl
"""

import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen 2.5 3B with QLoRA")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--output-dir", default="./fine_tuned", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        print("Unsloth not installed. Run: pip install unsloth")
        print("This script is designed for Google Colab with a T4 GPU.")
        return

    print("Loading base model …")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-3B-Instruct",
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    print("Loading dataset …")
    with open(args.dataset, encoding="utf-8") as f:
        data = [json.loads(line) for line in f]
    print(f"  {len(data)} examples loaded")

    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import Dataset

    dataset = Dataset.from_list(data)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        max_seq_length=2048,
        args=TrainingArguments(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            fp16=True,
            logging_steps=10,
            output_dir=args.output_dir,
            optim="adamw_8bit",
        ),
    )

    print("Training …")
    trainer.train()

    print("Saving model …")
    model.save_pretrained(os.path.join(args.output_dir, "lora_model"))
    tokenizer.save_pretrained(os.path.join(args.output_dir, "lora_model"))

    print(f"\nDone! LoRA adapter saved to {args.output_dir}/lora_model")
    print("To export to GGUF, use llama.cpp's convert script:")
    print(f"  python convert_lora_to_gguf.py {args.output_dir}/lora_model")


if __name__ == "__main__":
    main()
