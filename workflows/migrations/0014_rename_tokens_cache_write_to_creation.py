# Review Fix M3: align field name with API terminology (cache_creation, not cache_write)

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0013_feedback_unique_user_message"),
    ]

    operations = [
        migrations.RenameField(
            model_name="costlog",
            old_name="tokens_cache_write",
            new_name="tokens_cache_creation",
        ),
    ]
