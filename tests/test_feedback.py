import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from utim_cli.server.router import app
from utim_cli.server.db import SessionLocal, User, Feedback, init_db
from utim_cli.config import Config
from utim_cli.utim import SlashCommandCompleter, COMMANDS
from prompt_toolkit.document import Document

def test_feedback_system_and_permissions():
    init_db()
    db = SessionLocal()
    try:
        # Create users
        admin_user_1 = db.query(User).filter(User.email == 'admin1@utim.dev').first()
        if not admin_user_1:
            admin_user_1 = User(email='admin1@utim.dev', firebase_uid='JL763NoYOlRHV5WSkL9ySpz5gkI3')
            db.add(admin_user_1)
        else:
            admin_user_1.firebase_uid = 'JL763NoYOlRHV5WSkL9ySpz5gkI3'
            
        admin_user_2 = db.query(User).filter(User.email == 'admin2@utim.dev').first()
        if not admin_user_2:
            admin_user_2 = User(email='admin2@utim.dev', firebase_uid='HADaFqH9p0brRlMAs5mtEbwuBzk1')
            db.add(admin_user_2)
        else:
            admin_user_2.firebase_uid = 'HADaFqH9p0brRlMAs5mtEbwuBzk1'
            
        normal_user = db.query(User).filter(User.email == 'normal@utim.dev').first()
        if not normal_user:
            normal_user = User(email='normal@utim.dev', firebase_uid='some_other_uid')
            db.add(normal_user)
        else:
            normal_user.firebase_uid = 'some_other_uid'
            
        db.query(Feedback).delete()
        db.commit()
        db.refresh(admin_user_1)
        db.refresh(admin_user_2)
        db.refresh(normal_user)

        client = TestClient(app)

        # Helper to mock Firebase token verification returning specific user
        def mock_verify(token):
            payload = MagicMock()
            if token == 'admin_token_1':
                payload.email = 'admin1@utim.dev'
                payload.uid = 'JL763NoYOlRHV5WSkL9ySpz5gkI3'
                payload.name = 'Admin 1'
            elif token == 'admin_token_2':
                payload.email = 'admin2@utim.dev'
                payload.uid = 'HADaFqH9p0brRlMAs5mtEbwuBzk1'
                payload.name = 'Admin 2'
            else:
                payload.email = 'normal@utim.dev'
                payload.uid = 'some_other_uid'
                payload.name = 'Normal User'
            return payload

        with patch('utim_cli.server.firebase.verify_firebase_token', side_effect=mock_verify):
            # 1. Normal user submits feedback with chat history
            headers_normal = {'Authorization': 'Bearer normal_token'}
            chat_history = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"}
            ]
            resp_submit = client.post('/feedback/submit', json={
                'rating': 5,
                'comment': 'Excellent task execution',
                'chat_history': chat_history
            }, headers=headers_normal)
            assert resp_submit.status_code == 200
            assert resp_submit.json()['status'] == 'success'

            # Check feedback stored in DB
            fb = db.query(Feedback).filter(Feedback.user_id == normal_user.id).first()
            assert fb is not None
            assert fb.rating == 5
            assert fb.comment == 'Excellent task execution'
            assert 'hello' in fb.chat_history

            # 2. Normal user tries to list feedbacks -> Denied
            resp_list_normal = client.get('/feedback/list', headers=headers_normal)
            assert resp_list_normal.status_code == 403

            # 3. Admins list feedbacks -> Allowed
            headers_admin1 = {'Authorization': 'Bearer admin_token_1'}
            resp_list_admin1 = client.get('/feedback/list', headers=headers_admin1)
            assert resp_list_admin1.status_code == 200
            data_admin1 = resp_list_admin1.json()
            assert len(data_admin1) > 0
            assert data_admin1[0]['rating'] == 5
            assert data_admin1[0]['comment'] == 'Excellent task execution'
            assert data_admin1[0]['user_email'] == 'normal@utim.dev'
            assert data_admin1[0]['chat_history'][0]['content'] == 'hello'

            headers_admin2 = {'Authorization': 'Bearer admin_token_2'}
            resp_list_admin2 = client.get('/feedback/list', headers=headers_admin2)
            assert resp_list_admin2.status_code == 200

        # 4. Test TUI dynamic SlashCommandCompleter filtering
        completer = SlashCommandCompleter()

        # Admin user — only /feedbacks visible, no /feedback alias
        with patch('utim_cli.config.Config.get', return_value='JL763NoYOlRHV5WSkL9ySpz5gkI3'):
            completions = list(completer.get_completions(Document('/feedb'), None))
            cmd_names = [c.text for c in completions]
            assert 'feedbacks' in cmd_names
            assert 'feedback' not in cmd_names   # alias removed

        # Normal user — neither command visible
        with patch('utim_cli.config.Config.get', return_value='some_other_uid'):
            completions = list(completer.get_completions(Document('/feedb'), None))
            cmd_names = [c.text for c in completions]
            assert 'feedbacks' not in cmd_names
            assert 'feedback' not in cmd_names

    finally:
        db.close()


def test_tui_feedback_dialogs():
    from utim_cli.tui.feedback_dialog import _dialog_submit_feedback, _dialog_submit_feedback_conditional

    mock_orch = MagicMock()
    mock_orch.messages = [{"role": "user", "content": "TUI test"}]

    # ── Call-sequence reference ────────────────────────────────────────────────
    # _dialog_submit_feedback:
    #   call 1 → rating dialog
    #   (prompt → comment)
    #   call 2 → consent dialog  (idx 0 = allow, idx 1 = deny)
    #
    # _dialog_submit_feedback_conditional:
    #   call 1 → thumbs up/down
    #   call 2 → star rating
    #   (prompt → comment, only if rating != 5)
    #   call 3 → consent dialog

    CONSENT_ALLOW = ('select', 0)   # index 0 in consent rows = Allow
    CONSENT_DENY  = ('select', 1)   # index 1 in consent rows = Don't Allow

    # ── 1. rating 5, comment blank, consent Allow → chat_history sent ─────────
    with patch('utim_cli.config.config.get', side_effect=lambda key, default=None: 'dummy_key' if key == 'api_key' else None), \
         patch('utim_cli.utim._run_list_dialog', side_effect=[('select', 0), CONSENT_ALLOW]), \
         patch('prompt_toolkit.prompt', return_value='') as mock_prompt, \
         patch('requests.post') as mock_post:

        _dialog_submit_feedback(mock_orch)

        mock_prompt.assert_called_once()          # comment prompt is always shown
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['rating'] == 5
        assert kwargs['json']['comment'] is None  # empty string → None
        assert kwargs['json']['chat_history'][0]['content'] == 'TUI test'

    # ── 2. rating 4, comment filled, consent Allow → chat_history sent ────────
    with patch('utim_cli.config.config.get', side_effect=lambda key, default=None: 'dummy_key' if key == 'api_key' else None), \
         patch('utim_cli.utim._run_list_dialog', side_effect=[('select', 1), CONSENT_ALLOW]), \
         patch('prompt_toolkit.prompt', return_value='Very good!') as mock_prompt, \
         patch('requests.post') as mock_post:

        _dialog_submit_feedback(mock_orch)

        mock_prompt.assert_called_once()
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['rating'] == 4
        assert kwargs['json']['comment'] == 'Very good!'
        assert kwargs['json']['chat_history'][0]['content'] == 'TUI test'

    # ── 3. rating 4, consent Deny → chat_history is None ─────────────────────
    with patch('utim_cli.config.config.get', side_effect=lambda key, default=None: 'dummy_key' if key == 'api_key' else None), \
         patch('utim_cli.utim._run_list_dialog', side_effect=[('select', 1), CONSENT_DENY]), \
         patch('prompt_toolkit.prompt', return_value='Not great') as mock_prompt, \
         patch('requests.post') as mock_post:

        _dialog_submit_feedback(mock_orch)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['rating'] == 4
        assert kwargs['json']['comment'] == 'Not great'
        assert kwargs['json']['chat_history'] is None  # consent denied

    # ── 4. Conditional: Thumbs Up → rating 5, consent Allow ──────────────────
    with patch('utim_cli.config.config.get', side_effect=lambda key, default=None: 'dummy_key' if key == 'api_key' else None), \
         patch('utim_cli.utim._run_list_dialog', side_effect=[('select', 0), ('select', 0), CONSENT_ALLOW]), \
         patch('requests.post') as mock_post:

        # thumbs=up(0), rating=Excellent(0), consent=Allow
        with patch('prompt_toolkit.prompt', side_effect=AssertionError("Should not prompt for Excellent rating")):
            _dialog_submit_feedback_conditional(mock_orch)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['rating'] == 5
        assert kwargs['json']['comment'] is None
        assert kwargs['json']['chat_history'][0]['content'] == 'TUI test'

    # ── 5. Conditional: Thumbs Down → rating 2 (Poor), consent Allow ─────────
    with patch('utim_cli.config.config.get', side_effect=lambda key, default=None: 'dummy_key' if key == 'api_key' else None), \
         patch('utim_cli.utim._run_list_dialog', side_effect=[('select', 1), ('select', 1), CONSENT_ALLOW]), \
         patch('prompt_toolkit.prompt', return_value='Failed on git command') as mock_prompt, \
         patch('requests.post') as mock_post:

        # thumbs=down(1), rows filtered to [Average, Poor, Terrible]+cancel → index 1 = Poor(2)
        _dialog_submit_feedback_conditional(mock_orch)

        mock_prompt.assert_called_once()
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['rating'] == 2
        assert kwargs['json']['comment'] == 'Failed on git command'
        assert kwargs['json']['chat_history'][0]['content'] == 'TUI test'

    # ── 6. Conditional: Thumbs Down → rating 2, consent Deny → no chat ───────
    with patch('utim_cli.config.config.get', side_effect=lambda key, default=None: 'dummy_key' if key == 'api_key' else None), \
         patch('utim_cli.utim._run_list_dialog', side_effect=[('select', 1), ('select', 1), CONSENT_DENY]), \
         patch('prompt_toolkit.prompt', return_value='consent denied test') as mock_prompt, \
         patch('requests.post') as mock_post:

        _dialog_submit_feedback_conditional(mock_orch)

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs['json']['rating'] == 2
        assert kwargs['json']['chat_history'] is None  # consent denied
