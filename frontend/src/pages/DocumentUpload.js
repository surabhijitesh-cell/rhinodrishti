import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Upload, FileText, Trash2, RefreshCw, CheckCircle, AlertCircle, Clock } from "lucide-react";

export default function DocumentUpload({ api }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/uploaded-documents`);
      setDocuments(res.data.documents || []);
    } catch (e) {
      console.error("Failed to fetch documents:", e);
    }
  }, [api]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (file) => {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'text/plain'
    ];

    if (!allowedTypes.includes(file.type)) {
      setMessage({ type: 'error', text: 'File type not supported. Please upload PDF, Word, Excel, or TXT files.' });
      return;
    }

    setUploading(true);
    setMessage(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${api}/upload-document`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setMessage({ type: 'success', text: `Document "${res.data.filename}" uploaded successfully! AI analysis in progress...` });
      fetchDocuments();
    } catch (e) {
      setMessage({ type: 'error', text: e.response?.data?.detail || 'Failed to upload document' });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return;
    
    try {
      await axios.delete(`${api}/uploaded-documents/${docId}`);
      setMessage({ type: 'success', text: 'Document deleted successfully' });
      fetchDocuments();
    } catch (e) {
      setMessage({ type: 'error', text: 'Failed to delete document' });
    }
  };

  const getFileIcon = (fileType) => {
    switch (fileType) {
      case 'pdf': return '📄';
      case 'docx':
      case 'doc': return '📝';
      case 'xlsx':
      case 'xls': return '📊';
      default: return '📁';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Document Upload</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload offline intelligence materials (PDF, Word, Excel) for AI analysis
          </p>
        </div>
        <button
          onClick={fetchDocuments}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg hover:bg-accent/80 transition"
          data-testid="refresh-documents-btn"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-xl p-10 text-center transition-all ${
          dragActive
            ? 'border-primary bg-primary/5'
            : 'border-muted-foreground/30 hover:border-primary/50'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        data-testid="upload-dropzone"
      >
        <Upload className={`w-16 h-16 mx-auto mb-4 ${dragActive ? 'text-primary' : 'text-muted-foreground'}`} />
        <h3 className="text-lg font-semibold text-foreground mb-2">
          {dragActive ? 'Drop your file here' : 'Drag & drop your document'}
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          Supported formats: PDF, Word (.doc, .docx), Excel (.xls, .xlsx), TXT
        </p>
        <label className="cursor-pointer">
          <input
            type="file"
            className="hidden"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"
            onChange={handleFileInput}
            disabled={uploading}
            data-testid="file-input"
          />
          <span className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition">
            {uploading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Select File
              </>
            )}
          </span>
        </label>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            message.type === 'success'
              ? 'bg-green-500/10 text-green-500 border border-green-500/20'
              : 'bg-red-500/10 text-red-500 border border-red-500/20'
          }`}
          data-testid="upload-message"
        >
          {message.type === 'success' ? (
            <CheckCircle className="w-5 h-5" />
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          {message.text}
        </div>
      )}

      {/* Documents List */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground">
          Uploaded Documents ({documents.length})
        </h2>
        
        {documents.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No documents uploaded yet</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="bg-card border border-border rounded-lg p-4 flex items-start justify-between"
                data-testid={`document-card-${doc.id}`}
              >
                <div className="flex items-start gap-4">
                  <span className="text-3xl">{getFileIcon(doc.file_type)}</span>
                  <div>
                    <h3 className="font-semibold text-foreground">{doc.filename}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Uploaded: {new Date(doc.uploaded_at).toLocaleString()}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      {doc.processed ? (
                        <span className="flex items-center gap-1 text-xs text-green-500">
                          <CheckCircle className="w-3 h-3" />
                          AI Analyzed
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-yellow-500">
                          <Clock className="w-3 h-3" />
                          Processing...
                        </span>
                      )}
                      {doc.region && (
                        <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                          {doc.region}
                        </span>
                      )}
                    </div>
                    {doc.ai_analysis && (
                      <p className="text-sm text-muted-foreground mt-2 line-clamp-3">
                        {doc.ai_analysis}
                      </p>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="p-2 text-red-500 hover:bg-red-500/10 rounded-lg transition"
                  title="Delete document"
                  data-testid={`delete-doc-${doc.id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
