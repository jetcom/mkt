# Question Bank Enhancement Plan

## Phase 1: User Accounts & Authentication

### 1.1 Basic Auth Setup
- [ ] Add Django authentication (django.contrib.auth already available)
- [ ] Create login/logout pages
- [ ] Add registration page (or admin-only user creation)
- [ ] Protect all views with @login_required
- [ ] Add user display in navbar with logout button

### 1.2 User-Course Association
- [ ] Add `owner` field to Course model (ForeignKey to User)
- [ ] Add `collaborators` ManyToMany field to Course for sharing
- [ ] Filter courses/banks/questions by user permissions
- [ ] Add "My Courses" vs "Shared with me" views

### 1.3 Permissions
- [ ] Course owner has full control
- [ ] Collaborators can view and use questions, but not edit/delete
- [ ] Optional: Add role field (owner, editor, viewer)

## Phase 2: Multiple Exam Versions

### 2.1 Version Generation
- [ ] Add "Number of Versions" field to exam builder (1-10)
- [ ] Generate multiple PDFs with version letters (A, B, C...)
- [ ] Each version gets different random question selection from blocks
- [ ] Each version shuffles questions differently (if shuffle enabled)
- [ ] Print version letter on exam header

### 2.2 Answer Key Mapping
- [ ] Generate master answer key showing all versions
- [ ] Map question numbers across versions
- [ ] Option to download as ZIP (all versions + keys)

## Phase 3: Quick Wins

### 3.1 Full-Text Search
- [ ] Add PostgreSQL full-text search or use Django's SearchVector
- [ ] Search across question text, answers, tags
- [ ] Highlight matches in results

### 3.2 Keyboard Shortcuts
- [ ] `n` - New question
- [ ] `/` - Focus search
- [ ] `Escape` - Close modal
- [ ] Arrow keys - Navigate questions

### 3.3 Duplicate Detection
- [ ] Hash question text on save
- [ ] Warn when creating similar questions
- [ ] Show potential duplicates in UI

## Phase 4: AI Enhancements

### 4.1 Question Generation
- [ ] "Generate questions from topic" feature
- [ ] Generate wrong answers for multiple choice
- [ ] Improve/rephrase existing questions

### 4.2 Smart Tagging
- [ ] Auto-suggest tags based on question content
- [ ] Batch auto-tag existing questions

## Phase 5: LMS Integration

### 5.1 Export Formats
- [ ] QTI export for Canvas/Blackboard
- [ ] Moodle XML export
- [ ] CSV export with all metadata

### 5.2 Import Formats
- [ ] QTI import
- [ ] Canvas quiz import
- [ ] Blackboard import

---

## Implementation Order

**Starting Now:**
1. Phase 1.1 - Basic Auth (foundation for everything else)
2. Phase 2.1 - Multiple Versions (leverages existing mkt.py logic)

**Next Session:**
3. Phase 1.2 - User-Course Association
4. Phase 3.1 - Full-Text Search

**Future:**
5. Remaining phases based on priority
