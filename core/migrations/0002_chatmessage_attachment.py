from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatmessage',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='chat_uploads/'),
        ),
    ]
