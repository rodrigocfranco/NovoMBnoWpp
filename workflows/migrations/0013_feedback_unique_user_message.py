# Code review fix: add unique constraint on (user, message) to prevent duplicate feedbacks

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0012_merge_20260315_1227"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feedback",
            name="rating",
            field=models.CharField(
                choices=[
                    ("positive", "Positivo"),
                    ("negative", "Negativo"),
                    ("comment", "Comentário"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="feedback",
            constraint=models.UniqueConstraint(
                fields=["user", "message"],
                name="unique_feedback_per_message",
            ),
        ),
    ]
