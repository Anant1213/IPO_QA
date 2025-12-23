# Database-Integrated Upload Endpoint
# This file contains the replacement code for app.py upload endpoint

@app.route('/api/upload', methods=['POST'])
def upload_and_process():
    """Upload and process PDF document - saves to database"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"File uploaded: {filename}")
        
        # Calculate hash
        file_hash = get_file_hash(filepath)
        
        # Check for duplicate
        duplicate = check_duplicate(file_hash)
        if duplicate:
            os.remove(filepath)
            return jsonify({
                'error': 'Duplicate file',
                'message': f'This document already exists as "{duplicate["display_name"]}"',
                'existing_document': duplicate
            }), 409
        
        # Generate document ID
        document_id = generate_document_id(filename)
        doc_folder = os.path.join(app.config['DOCUMENTS_FOLDER'], document_id)
        os.makedirs(doc_folder, exist_ok=True)
        
        print(f"Processing document: {document_id}")
        
        # Extract pages
        pages = extract_pages(filepath)
        
        # Detect chapters and build chunks
        from utils.text_utils import detect_chapters, build_chunks
        chapters = detect_chapters(pages)
        chunks = build_chunks(pages, chapters)
        
        print(f"Extracted {len(chunks)} chunks from {len(pages)} pages")
        
        # Generate embeddings
        from utils.embedding_utils import get_embedding_model
        model = get_embedding_model()
        chunk_texts = [c['text'] for c in chunks]
        embeddings_array = model.encode(chunk_texts, convert_to_numpy=True, show_progress_bar=True)
        
        print(f"Generated embeddings for {len(embeddings_array)} chunks")
        
        # Create document in database
        doc_data = {
            'document_id': document_id,
            'filename': filename,
            'display_name': os.path.splitext(filename)[0].replace('_', ' ').title(),
            'file_hash': file_hash,
            'file_path': filepath,
            'total_pages': len(pages),
            'total_chunks': len(chunks),
            'doc_metadata': {
                'total_chapters': len(chapters),
                'upload_date': datetime.now().isoformat()
            }
        }
        
        doc_result = DocumentRepository.create(doc_data)
        doc_db_id = doc_result['id']
        
        print(f"Created document in database: ID={doc_db_id}")
        
        # Prepare chunks for bulk insert
        chunks_data = []
        for idx, chunk in enumerate(chunks):
            chunks_data.append({
                'document_id': doc_db_id,
                'chunk_index': idx,
                'text': chunk['text'],
                'page_number': chunk.get('page_number'),
                'word_count': len(chunk['text'].split()),
                'chunk_metadata': {
                    'page_numbers': chunk.get('page_numbers', []),
                    'chapter': chunk.get('chapter', '')
                }
            })
        
        # Bulk insert chunks
        chunk_ids = ChunkRepository.create_many(chunks_data)
        print(f"Inserted {len(chunk_ids)} chunks")
        
        # Prepare embeddings for bulk insert
        embeddings_data = []
        for chunk_id, embedding in zip(chunk_ids, embeddings_array):
            embeddings_data.append({
                'chunk_id': chunk_id,
                'embedding': embedding.tolist(),
                'model_name': 'all-MiniLM-L6-v2'
            })
        
        # Bulk insert embeddings
        emb_count = EmbeddingRepository.create_many(embeddings_data)
        print(f"Inserted {emb_count} embeddings")
        
        # Update document with final counts
        DocumentRepository.update(document_id, {
            'total_chunks': len(chunks),
            'processed_at': datetime.now()
        })
        
        print(f"Document processed successfully: {document_id}")
        
        # Return document metadata
        final_doc = DocumentRepository.get_by_id(document_id)
        
        return jsonify({
            'document': final_doc,
            'message': f'Successfully processed {filename} ({len(chunks)} chunks, {len(pages)} pages)'
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
