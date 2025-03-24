
class Config:
    def __init__(self, config_dict: Dict = None):
        self.config_dict = config_dict or {}

    def get(self, key: str, default: Any = None):
        return self.config_dict.get(key, default)

    @staticmethod
    def load_file(config_path: str):
        """Loads configuration from a YAML or JSON file."""
        try:
            with open(config_path, "r") as file:
                if config_path.endswith((".yml", ".yaml")):
                    config_data = yaml.safe_load(file)
                else:
                    config_data = json.load(file)
            return Config(config_data)
        except (FileNotFoundError, json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValueError(f"Error loading config file {config_path}: {e}")


class ArtifactStore:
    """Stores and retrieves intermediate artifacts for the pipeline."""

    def __init__(self, config):
        self.config = config
        self.base_path = self.config.get("folder_path", {}).get(
            "artifacts", "artifacts"
        )
        os.makedirs(self.base_path, exist_ok=True)
        # logging.info(f"Artifact store initialized at '{self.base_path}'")

    def save_artifact(
        self,
        artifact: Any,
        subdir: str,
        name: str,
    ) -> None:
        """Save an artifact in the specified format."""
        artifact_dir = os.path.join(self.base_path, subdir)
        os.makedirs(artifact_dir, exist_ok=True)
        artifact_path = os.path.join(artifact_dir, name)

        if name.endswith(".pkl"):
            with open(artifact_path, "wb") as f:
                pickle.dump(artifact, f)
        elif name.endswith(".csv"):
            if isinstance(artifact, pd.DataFrame):
                artifact.to_csv(artifact_path, index=False)
            else:
                raise ValueError("CSV format only supports pandas DataFrames.")
        else:
            raise ValueError(f"Unsupported format for {name}")
        logging.info(f"Artifact '{name}' saved to {artifact_path}")

    def load_artifact(
        self,
        subdir: str,
        name: str,
    ):
        """Load an artifact in the specified format."""
        artifact_path = os.path.join(self.base_path, subdir, name)
        if os.path.exists(artifact_path):
            if name.endswith(".pkl"):
                with open(artifact_path, "rb") as f:
                    artifact = pickle.load(f)
            elif name.endswith(".csv"):
                artifact = pd.read_csv(artifact_path)
            else:
                raise ValueError(f"Unsupported format for {name}")
            logging.info(f"Artifact '{name}' loaded from {artifact_path}")
            return artifact
        else:
            logging.warning(f"Artifact '{name}' not found in {artifact_path}")
            return None


# ----------------------------- 
# Data Ingestion
# -----------------------------

class DataIngestion:

    def __init__(self, config):
        self.config = config
        self.artifact_store = ArtifactStore(config)

    def data_ingestion(self, path):
      
        # Load raw data
        df = pd.read_csv(path)
        # Split data
        test_size = self.config.get("base",{}).get("test_size",{})
        train_data, test_data = train_test_split(df, test_size=test_size, random_state=42)
        logging.info(
            f"Data split complete. Train shape: {train_data.shape}, Test shape: {test_data.shape}"
        )
        # Save raw artifacts
        self.artifact_store.save_artifact(
            train_data, subdir=raw_path, name=raw_train_filename 
        )
        self.artifact_store.save_artifact(
            test_data, subdir=raw_path, name=raw_test_filename
        )
        logging.info("Data ingestion completed")
        return train_data, test_data

# ----------------------------- 
# Training Pipeline
# -----------------------------

class TrainingPipeline:
    """Main pipeline class that orchestrates the training workflow."""

    def __init__(self, data_path: str, config_path: str = "config/config.yml"):
        self.data_path = data_path
        self.config = Config.load_file(config_path).config_dict

        
    def run(self) -> Tuple[str, StackPipeline]:
        """Execute the training pipeline."""
        # Create stack
        pipe = StackPipeline(name="training_pipeline", config=self.config)

        dataingest = DataIngestion()
        
        # Add tasks to pipeline
        pipe.add_task(dataingest.data_ingestion(self.path,self.config))
        pipe.add_task(DataProcessing(dataingest.data_ingestion(self.path,self.config)))
        # pipe.add_task(ModelTrainingTask(model_type=stack.config.get("model.type", "default")))
        # pipe.add_task(ModelEvaluationTask())
        
        # Run the pipeline
        try:
            run_id = pipe.run()
            logging.info(f"Pipeline completed successfully with run ID: {run_id}")
            
            # Output run summary
            self._print_run_summary(pipe, run_id)
            
            return run_id, pipe
            
        except Exception as e:
            logging.error(f"Pipeline execution failed: {str(e)}")
            raise
            
    def _print_run_summary(self, stack: StackPipeline, run_id: str) -> None:
        """Print a summary of the pipeline run."""
        # List artifacts
        artifacts = stack.artifact_store.list_artifacts(run_id)
        print(f"\nRun ID: {run_id}")
        print("\nArtifacts:")
        for uri in artifacts:
            print(f"- {uri}")
            
        # Get run details
        run_details = pipe.get_run_details(run_id)
        print("\nRun Details:")
        print(f"Pipeline: {run_details.get('pipeline_name')}")
        print(f"Status: {run_details.get('status')}")
        print(f"Duration: {run_details.get('duration_seconds', 0):.2f} seconds")
        
        # Check if run was successful
        if run_details.get("status") == "completed":
            print("Pipeline completed successfully")
            
            # Print evaluation metrics if available
            # metrics = stack.artifact_store.load_artifact("metrics", "evaluation_metrics.json")
            # if metrics:
            #     print("\nEvaluation Metrics:")
            #     for metric, value in metrics.items():
            #         print(f"- {metric}: {value:.4f}")


# ----------------------------- 
# Example Usage
# ----------------------------- 

def main():
    """Main entry point for running the pipeline."""
    # Path to your data file
    data_path = "data.csv"
    
    # Create and run the pipeline
    try:
        pipeline = TrainingPipeline(data_path)
        run_id, pipe = pipeline.run()
        
        print("\n" + "="*50)
        print("Pipeline execution complete!")
        print(f"Run ID: {run_id}")
        print("="*50)
        
        return run_id, pipe
        
    except Exception as e:
        print(f"\nError running pipeline: {str(e)}")
        return None, None


if __name__ == "__main__":
    main()
