# Databricks Auto Loader example (run in Databricks Notebook or Job)
# Requires Unity Catalog external location to S3 path and appropriate permissions.

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

s3_path = "s3://YOUR_BUCKET/YOUR_PREFIX/"  # e.g., s3://my-bucket/imdb/
checkpoint_path = "s3://YOUR_BUCKET/checkpoints/imdb_autoloader/"  # a durable checkpoint location

df = (spark.readStream
      .format("cloudFiles")
      .option("cloudFiles.format", "json")
      .option("cloudFiles.inferColumnTypes", "true")
      .option("cloudFiles.schemaEvolutionMode", "rescued")
      .option("cloudFiles.includeExistingFiles", "true")
      .load(s3_path))

# Write into a Delta table with schema evolution and rescued data automatically handled
(df.writeStream
   .format("delta")
   .option("checkpointLocation", checkpoint_path)
   .option("mergeSchema", "true")
   .outputMode("append")
   .toTable("catalog.schema.imdb_titles"))

# Alternatively: write to a location
# (df.writeStream
#    .format("delta")
#    .option("checkpointLocation", checkpoint_path)
#    .option("mergeSchema", "true")
#    .outputMode("append")
#    .start("s3://YOUR_BUCKET/delta/imdb_titles/"))
